import yaml
import json
import os
from pathlib import Path
from typing import Dict, Any
from utils.logger import get_logger

logger = get_logger(__name__)

class SmartConfigMerger:
    def __init__(self, framework_root: str = "framework"):
        self.framework_root = Path(framework_root)
        self.global_config = self._load_global_config()
        self.framework_defaults = self._load_framework_defaults()
    
    def _load_global_config(self) -> Dict[str, Any]:
        """Load global framework configuration"""
        global_config_path = self.framework_root / "config" / "global.yaml"
        
        if global_config_path.exists():
            with open(global_config_path, 'r') as f:
                config = yaml.safe_load(f)
                logger.info(f"Loaded global config from {global_config_path}")
                return config
        
        logger.warning(f"Global config not found at {global_config_path}")
        return {}
    
    def _load_framework_defaults(self) -> Dict[str, Dict[str, Any]]:
        """Load all framework-specific default configurations"""
        defaults = {}
        defaults_dir = self.framework_root / "defaults"
        
        if not defaults_dir.exists():
            logger.warning(f"Defaults directory not found: {defaults_dir}")
            return defaults
        
        for defaults_file in defaults_dir.glob("*.defaults.yaml"):
            framework_name = defaults_file.stem.replace('.defaults', '')
            
            try:
                with open(defaults_file, 'r') as f:
                    framework_config = yaml.safe_load(f)
                    defaults[framework_name] = framework_config
                    logger.info(f"Loaded {framework_name} defaults from {defaults_file}")
            except Exception as e:
                logger.error(f"Failed to load {defaults_file}: {e}")
        
        return defaults
    
    def merge_config(self, app_config: Dict[str, Any], detected_framework: str) -> Dict[str, Any]:
        """Merge app configuration with smart defaults"""
        logger.info(f"Merging configuration for {detected_framework} application")
        
        # Start with global framework configuration
        merged = self._deep_merge({}, self.global_config)
        
        # Add framework-specific defaults
        framework_defaults = self.framework_defaults.get(detected_framework, {})
        merged = self._deep_merge(merged, framework_defaults)
        
        # Apply app-specific configuration (highest priority)
        merged = self._deep_merge(merged, app_config)
        
        # Add environment-specific overrides
        merged = self._add_environment_overrides(merged)
        
        # Add auto-detected values
        merged = self._add_auto_detected_values(merged, app_config, detected_framework)
        
        logger.info(f"Configuration merge completed for {merged.get('app', {}).get('name', 'unknown')}")
        return merged
    
    def _deep_merge(self, base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
        """Recursively merge dictionaries, with override taking precedence"""
        result = base.copy()
        
        for key, value in override.items():
            if (key in result and 
                isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        
        return result
    
    def _add_environment_overrides(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Add environment-specific configuration overrides"""
        
        # Azure DevOps environment variables
        if os.getenv('BUILD_BUILDNUMBER'):
            build_number = os.getenv('BUILD_BUILDNUMBER')
            config['build_info'] = {
                'build_number': build_number,
                'build_id': os.getenv('BUILD_BUILDID'),
                'source_version': os.getenv('BUILD_SOURCEVERSION', '')[:8],  # Short commit SHA
                'source_branch': os.getenv('BUILD_SOURCEBRANCHNAME', 'unknown'),
                'pipeline_name': os.getenv('BUILD_DEFINITIONNAME', 'unknown'),
                'build_reason': os.getenv('BUILD_REASON', 'manual')
            }
        
        return config
    
    def _add_auto_detected_values(self, config: Dict[str, Any], 
                                 original_config: Dict[str, Any], 
                                 detected_framework: str) -> Dict[str, Any]:
        """Add auto-detected values and smart defaults"""
        
        # Ensure app section exists
        if 'app' not in config:
            config['app'] = {}
        
        # Auto-detect app name if not provided
        if 'name' not in config['app']:
            # Try to get from original config, environment, or repository
            app_name = (original_config.get('app', {}).get('name') or
                       os.getenv('BUILD_REPOSITORY_NAME', 'unknown-app'))
            config['app']['name'] = app_name.lower().replace('_', '-')
        
        # Set detected framework
        config['app']['framework'] = detected_framework
        config['app']['detected_framework'] = detected_framework
        
        # Auto-configure source information
        if 'source' not in config:
            config['source'] = {}
        
        source_config = config['source']
        source_config['repo_url'] = os.getenv('BUILD_REPOSITORY_URI', 
                                             source_config.get('repo_url', ''))
        source_config['branch'] = os.getenv('BUILD_SOURCEBRANCHNAME', 
                                           source_config.get('branch', 'main'))
        source_config['commit_sha'] = os.getenv('BUILD_SOURCEVERSION', '')
        
        # Auto-configure Docker settings
        if 'docker' not in config:
            config['docker'] = {}
        
        docker_config = config['docker']
        if 'repository' not in docker_config:
            docker_config['repository'] = os.getenv('DOCKER_REPOSITORY', 
                                                   self.global_config.get('docker', {}).get('organization', 'myorg'))
        
        if 'image' not in docker_config:
            docker_config['image'] = config['app']['name']
        
        # Generate image tags
        build_number = os.getenv('BUILD_BUILDNUMBER', 'local')
        docker_config['tag'] = f"v{build_number}"
        docker_config['full_image'] = f"{docker_config['repository']}/{docker_config['image']}:{docker_config['tag']}"
        docker_config['latest_image'] = f"{docker_config['repository']}/{docker_config['image']}:latest"
        
        # Auto-configure deployment settings
        if 'deployment' not in config:
            config['deployment'] = {}
        
        deployment_config = config['deployment']
        if 'namespace' not in deployment_config:
            deployment_config['namespace'] = config['app']['name']
        
        if 'environment' not in deployment_config:
            branch = source_config.get('branch', 'unknown')
            if branch in ['main', 'master']:
                deployment_config['environment'] = 'production'
            elif branch == 'develop':
                deployment_config['environment'] = 'staging'
            else:
                deployment_config['environment'] = 'development'
        
        return config
    
    def validate_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize the merged configuration"""
        errors = []
        warnings = []
        
        # Validate required fields
        if not config.get('app', {}).get('name'):
            errors.append("app.name is required")
        
        if not config.get('docker', {}).get('repository'):
            errors.append("docker.repository is required")
        
        # Validate resource specifications
        if 'deployment' in config and 'resources' in config['deployment']:
            resources = config['deployment']['resources']
            if 'limits' in resources and 'requests' in resources:
                # Ensure requests don't exceed limits
                limits = resources['limits']
                requests = resources['requests']
                
                if 'cpu' in both and self._parse_cpu(requests['cpu']) > self._parse_cpu(limits['cpu']):
                    warnings.append("CPU request exceeds limit")
                
                if 'memory' in both and self._parse_memory(requests['memory']) > self._parse_memory(limits['memory']):
                    warnings.append("Memory request exceeds limit")
        
        config['validation'] = {
            'errors': errors,
            'warnings': warnings,
            'valid': len(errors) == 0
        }
        
        return config
    
    def _parse_cpu(self, cpu_str: str) -> float:
        """Parse CPU string to comparable float (in millicores)"""
        if cpu_str.endswith('m'):
            return float(cpu_str[:-1])
        return float(cpu_str) * 1000
    
    def _parse_memory(self, memory_str: str) -> int:
        """Parse memory string to comparable int (in bytes)"""
        memory_str = memory_str.upper()
        if memory_str.endswith('KI'):
            return int(memory_str[:-2]) * 1024
        elif memory_str.endswith('MI'):
            return int(memory_str[:-2]) * 1024 * 1024
        elif memory_str.endswith('GI'):
            return int(memory_str[:-2]) * 1024 * 1024 * 1024
        return int(memory_str)