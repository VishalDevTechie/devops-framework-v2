import os
import json
import re
from pathlib import Path
from typing import Tuple, Dict, Optional

class FrameworkDetector:
    def __init__(self):
        self.detection_patterns = {
            'angular': {
                'files': ['angular.json', 'src/main.ts', 'src/app/app.module.ts'],
                'package_dependencies': ['@angular/core', '@angular/cli', '@angular/common'],
                'package_dev_dependencies': ['@angular/cli', '@angular-devkit/build-angular'],
                'config_files': ['angular.json', 'tsconfig.json', 'tsconfig.app.json'],
                'build_commands': ['build:prod', 'build', 'ng build'],
                'start_commands': ['start', 'serve', 'ng serve'],
                'weight': 1.0
            },
            'react': {
                'files': ['src/App.js', 'src/App.tsx', 'public/index.html', 'src/index.js'],
                'package_dependencies': ['react', 'react-dom'],
                'package_dev_dependencies': ['react-scripts', 'create-react-app'],
                'config_files': ['package.json'],
                'build_commands': ['build', 'react-scripts build'],
                'start_commands': ['start', 'react-scripts start'],
                'weight': 0.9
            },
            'vue': {
                'files': ['src/App.vue', 'vue.config.js', 'src/main.js'],
                'package_dependencies': ['vue'],
                'package_dev_dependencies': ['@vue/cli-service', '@vue/cli'],
                'config_files': ['vue.config.js'],
                'build_commands': ['build', 'vue-cli-service build'],
                'start_commands': ['serve', 'vue-cli-service serve'],
                'weight': 0.8
            },
            'nextjs': {
                'files': ['next.config.js', 'pages/_app.js', 'pages/index.js'],
                'package_dependencies': ['next', 'react'],
                'package_dev_dependencies': ['next'],
                'config_files': ['next.config.js'],
                'build_commands': ['build', 'next build'],
                'start_commands': ['dev', 'next dev'],
                'weight': 0.9
            }
        }
    
    def detect_framework(self, repo_path: str) -> Tuple[str, float, Dict]:
        """Auto-detect application framework with confidence scoring"""
        print(f" Detecting framework in: {repo_path}")
        
        if not os.path.exists(repo_path):
            print(f"Repository path does not exist: {repo_path}")
            return 'unknown', 0.0, {}
        
        scores = {}
        detection_details = {}
        
        # Load package.json for dependency analysis
        package_json_data = self._load_package_json(repo_path)
        
        for framework, patterns in self.detection_patterns.items():
            score = 0
            details = {
                'files_found': [],
                'dependencies_found': [],
                'dev_dependencies_found': [],
                'config_files_found': [],
                'build_commands_available': [],
                'confidence_breakdown': {}
            }
            
            # Check for framework-specific files (high weight)
            file_score = 0
            for file_pattern in patterns['files']:
                file_path = Path(repo_path) / file_pattern
                if file_path.exists():
                    file_score += 3
                    details['files_found'].append(file_pattern)
            details['confidence_breakdown']['files'] = file_score
            score += file_score
            
            # Check package.json dependencies (highest weight)
            if package_json_data:
                deps = package_json_data.get('dependencies', {})
                dev_deps = package_json_data.get('devDependencies', {})
                
                dep_score = 0
                for dep in patterns['package_dependencies']:
                    if dep in deps:
                        dep_score += 5  # High weight for runtime dependencies
                        details['dependencies_found'].append(dep)
                
                dev_dep_score = 0
                for dep in patterns['package_dev_dependencies']:
                    if dep in dev_deps:
                        dev_dep_score += 3  # Medium weight for dev dependencies
                        details['dev_dependencies_found'].append(dep)
                
                details['confidence_breakdown']['dependencies'] = dep_score
                details['confidence_breakdown']['dev_dependencies'] = dev_dep_score
                score += dep_score + dev_dep_score
            
            # Check for configuration files (medium weight)
            config_score = 0
            for config_file in patterns['config_files']:
                config_path = Path(repo_path) / config_file
                if config_path.exists():
                    config_score += 2
                    details['config_files_found'].append(config_file)
            details['confidence_breakdown']['config_files'] = config_score
            score += config_score
            
            # Check available build commands (low weight)
            if package_json_data:
                scripts = package_json_data.get('scripts', {})
                build_score = 0
                for build_cmd in patterns['build_commands']:
                    if build_cmd in scripts:
                        build_score += 1
                        details['build_commands_available'].append(build_cmd)
                details['confidence_breakdown']['build_commands'] = build_score
                score += build_score
            
            # Apply framework weight
            weighted_score = score * patterns['weight']
            
            if weighted_score > 0:
                scores[framework] = weighted_score
                detection_details[framework] = details
                
                print(f"  {framework}: {weighted_score:.1f} points")
                print(f"    Files: {len(details['files_found'])}")
                print(f"    Dependencies: {len(details['dependencies_found'])}")
                print(f"    Dev Dependencies: {len(details['dev_dependencies_found'])}")
        
        # Determine best match
        if scores:
            detected_framework = max(scores, key=scores.get)
            max_score = scores[detected_framework]
            
            # Normalize confidence (max possible score estimation)
            max_possible = 50  # Rough estimate of maximum possible score
            confidence = min(max_score / max_possible, 1.0)
            
            print(f"✅ Detected: {detected_framework} (confidence: {confidence:.1%})")
            return detected_framework, confidence, detection_details[detected_framework]
        
        print("❓ No framework detected with confidence")
        return 'generic', 0.1, {}
    
    def detect_build_strategy(self, repo_path: str, framework: str) -> Dict:
        """Detect optimal build strategy for the detected framework"""
        package_json_data = self._load_package_json(repo_path)
        
        if not package_json_data:
            return {
                'command': 'echo "No package.json found"',
                'type': 'generic',
                'install_command': 'echo "No install needed"'
            }
        
        scripts = package_json_data.get('scripts', {})
        framework_patterns = self.detection_patterns.get(framework, {})
        
        # Determine install command
        install_command = "npm ci --prefer-offline --no-audit --no-fund"
        if not Path(repo_path).joinpath('package-lock.json').exists():
            install_command = "npm install --prefer-offline --no-audit --no-fund"
        
        # Find the best available build command
        preferred_commands = framework_patterns.get('build_commands', ['build'])
        
        for cmd in preferred_commands:
            if cmd in scripts:
                return {
                    'command': f'npm run {cmd}',
                    'type': framework,
                    'script_content': scripts[cmd],
                    'install_command': install_command,
                    'available_scripts': list(scripts.keys())
                }
        
        # Fallback to generic build
        if 'build' in scripts:
            return {
                'command': 'npm run build',
                'type': 'generic',
                'script_content': scripts['build'],
                'install_command': install_command
            }
        
        return {
            'command': install_command,
            'type': 'install-only',
            'install_command': install_command
        }
    
    def _load_package_json(self, repo_path: str) -> Optional[Dict]:
        """Load and parse package.json"""
        package_json_path = Path(repo_path) / 'package.json'
        
        if not package_json_path.exists():
            return None
        
        try:
            with open(package_json_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            print(f"⚠️ Failed to parse package.json: {e}")
            return None
    
    def detect_output_directory(self, repo_path: str, framework: str, app_name: str) -> str:
        """Detect the build output directory"""
        framework_patterns = self.detection_patterns.get(framework, {})
        
        # Check framework-specific default locations
        if framework == 'angular':
            possible_dirs = [
                f"dist/{app_name}",
                "dist",
                f"dist/{app_name}-app"
            ]
        elif framework == 'react':
            possible_dirs = ["build", "dist"]
        elif framework == 'vue':
            possible_dirs = ["dist", "build"]
        else:
            possible_dirs = ["dist", "build", "public"]
        
        # Check which directories exist after build
        for dir_path in possible_dirs:
            full_path = Path(repo_path) / dir_path
            if full_path.exists() and any(full_path.iterdir()):
                return dir_path
        
        return "dist"  # Default fallback