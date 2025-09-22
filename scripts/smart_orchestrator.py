# scripts/smart_orchestrator.py
import os
import json
import time
from pathlib import Path
from typing import Dict, Any, Optional
from framework_detector import FrameworkDetector
from config_merger import SmartConfigMerger
try:
    from smart_build import run as build_run
    from smart_docker import run as docker_run
    from smart_deploy import run as deploy_run
except ImportError as e:
    logger.error(f"Failed to import required modules: {e}")
    raise Exception(f"Missing required framework modules: {e}")
from utils.logger import get_logger

logger = get_logger(__name__)

class SmartOrchestrator:
    """
    Main orchestrator for the smart DevOps framework
    Handles analysis, build, containerization, and deployment
    """
    
    def __init__(self, framework_root: str = "framework"):
        self.framework_root = framework_root
        self.detector = FrameworkDetector()
        self.config_merger = SmartConfigMerger(framework_root)
        logger.info(" Smart Orchestrator initialized")
    
    def analyze_only(self, repo_path: str) -> Dict[str, Any]:
        """
        Analysis-only mode: detect framework and generate configuration
        Used by the SmartAnalysis stage in Azure Pipeline
        """
        logger.info(" Starting analysis-only mode")
        start_time = time.time()
        
        try:
            # Step 1: Validate repository path
            if not Path(repo_path).exists():
                raise Exception(f"Repository path does not exist: {repo_path}")
            
            logger.info(f"Analyzing repository: {repo_path}")
            
            # Step 2: Detect framework
            framework, confidence, detection_details = self.detector.detect_framework(repo_path)
            logger.info(f"Framework detected: {framework} (confidence: {confidence:.1%})")
            
            if confidence < 0.3:
                logger.warning("Low confidence detection - using generic configuration")
            
            # Step 3: Detect build strategy
            build_strategy = self.detector.detect_build_strategy(repo_path, framework)
            
            # Step 4: Create base configuration
            base_config = {
                'app': {
                    'name': self._extract_app_name(repo_path),
                    'framework': framework
                },
                'detection': {
                    'framework': framework,
                    'confidence': confidence,
                    'details': detection_details
                },
                'build_strategy': build_strategy
            }
            
            # Step 5: Merge with smart defaults
            merged_config = self.config_merger.merge_config(base_config, framework)
            
            # Step 6: Validate configuration
            final_config = self.config_merger.validate_config(merged_config)
            
            end_time = time.time()
            analysis_duration = end_time - start_time
            
            logger.info(f" Analysis completed in {analysis_duration:.2f}s")
            
            return {
                'success': True,
                'config': final_config,
                'duration': analysis_duration,
                'framework': framework,
                'confidence': confidence
            }
            
        except Exception as e:
            logger.error(f" Analysis failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def process_repository(self, repo_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        Full processing: build, containerize (and optionally deploy)
        Used by the SmartBuild stage in Azure Pipeline
        """
        logger.info(" Starting repository processing")
        start_time = time.time()
        
        try:
            # Validate inputs
            if not Path(repo_path).exists():
                raise Exception(f"Repository path does not exist: {repo_path}")
            
            if not config.get('success', True):
                raise Exception("Invalid configuration provided")
            
            app_name = config['app']['name']
            framework = config['app']['framework']
            
            logger.info(f"Processing {app_name} ({framework} application)")
            
            # Step 1: Build application
            logger.info(" Starting build process")
            build_result = build_run(config, repo_path)
            
            if not build_result['success']:
                raise Exception(f"Build failed: {build_result.get('error', 'Unknown build error')}")
            
            logger.info(" Build completed successfully")
            
            # Step 2: Containerize application
            logger.info(" Starting Docker process")
            docker_result = docker_run(config, repo_path)
            
            if not docker_result['success']:
                raise Exception(f"Docker process failed: {docker_result.get('error', 'Unknown Docker error')}")
            
            logger.info(" Docker process completed successfully")
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            logger.info(f" Repository processing completed in {total_duration:.2f}s")
            
            return {
                'success': True,
                'duration': total_duration,
                'build_result': build_result,
                'docker_result': docker_result,
                'app_name': app_name,
                'framework': framework
            }
            
        except Exception as e:
            logger.error(f" Repository processing failed: {str(e)}")
            return {
                'success': False,
                'error': str(e),
                'duration': time.time() - start_time
            }
    
    def full_pipeline(self, repo_path: str, deploy: bool = True) -> Dict[str, Any]:
        """
        Complete pipeline: analyze, build, containerize, and deploy
        For comprehensive testing and standalone execution
        """
        logger.info(" Starting full pipeline")
        
        # Step 1: Analysis
        analysis_result = self.analyze_only(repo_path)
        if not analysis_result['success']:
            return analysis_result
        
        config = analysis_result['config']
        
        # Step 2: Build and containerize
        process_result = self.process_repository(repo_path, config)
        if not process_result['success']:
            return process_result
        
        # Step 3: Deploy (if requested)
        deploy_result = None
        if deploy:
            logger.info(" Starting deployment")
            deploy_result = deploy_run(config)
        
        return {
            'success': True,
            'analysis': analysis_result,
            'processing': process_result,
            'deployment': deploy_result
        }
    
    def _extract_app_name(self, repo_path: str) -> str:
        """Extract application name from repository"""
        
        # Try to get from package.json
        package_json_path = Path(repo_path) / 'package.json'
        if package_json_path.exists():
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                    if 'name' in package_data:
                        name = package_data['name']
                        # Clean the name
                        return name.lower().replace('_', '-').replace('@', '').replace('/', '-')
            except:
                pass
        
        # Try to get from environment (Azure DevOps)
        if os.getenv('BUILD_REPOSITORY_NAME'):
            return os.getenv('BUILD_REPOSITORY_NAME').lower().replace('_', '-')
        
        # Fallback to directory name
        return Path(repo_path).name.lower().replace('_', '-')

# Standalone execution for testing
if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python smart_orchestrator.py <repo_path> [--deploy]")
        sys.exit(1)
    
    repo_path = sys.argv[1]
    deploy = "--deploy" in sys.argv
    
    orchestrator = SmartOrchestrator()
    result = orchestrator.full_pipeline(repo_path, deploy)
    
    if result['success']:
        print(" Pipeline completed successfully!")
    else:
        print(f" Pipeline failed: {result.get('error')}")
        sys.exit(1)