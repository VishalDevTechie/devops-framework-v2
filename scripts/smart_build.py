# Smart Build Module - scripts/smart_build.py

import os
import json
import time
from pathlib import Path
from typing import Dict, Any
from utils.logger import get_logger
from utils.helpers import run_command, ensure_directory, find_files

logger = get_logger(__name__)

def run(config: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
    """Smart build process with auto-detection and framework-specific optimization"""
    logger.info(" Starting Smart Build Process")
    start_time = time.time()
    
    # Validate inputs
    if not Path(repo_path).exists():
        raise Exception(f"Repository path does not exist: {repo_path}")
    
    build_strategy = config.get('build_strategy', {})
    app_name = config['app']['name']
    framework = config['app']['framework']
    
    logger.info(f"Building {app_name} ({framework} application)")
    
    # Change to repository directory
    original_dir = os.getcwd()
    os.chdir(repo_path)
    
    try:
        # Step 1: Verify project structure
        _verify_project_structure(framework)
        
        # Step 2: Install dependencies
        install_result = _install_dependencies(build_strategy)
        if not install_result['success']:
            raise Exception(f"Dependency installation failed: {install_result['stderr']}")
        
        # Step 3: Run build command
        build_result = _execute_build(build_strategy)
        if not build_result['success']:
            raise Exception(f"Build failed: {build_result['stderr']}")
        
        # Step 4: Verify build artifacts
        artifacts_info = _verify_build_artifacts(build_strategy, app_name, framework)
        
        # Step 5: Optimize artifacts (if needed)
        _optimize_artifacts(artifacts_info, framework)
        
        end_time = time.time()
        build_duration = end_time - start_time
        
        logger.info(f" Smart Build completed successfully in {build_duration:.2f}s")
        
        # Store build info in config for next stages
        config['build_info'] = {
            'output_dir': artifacts_info['output_dir'],
            'artifacts_count': artifacts_info['file_count'],
            'build_size': artifacts_info['total_size'],
            'duration': build_duration
        }
        
        return {
            'success': True,
            'duration': build_duration,
            'artifacts': artifacts_info,
            'install_result': install_result,
            'build_result': build_result
        }
        
    finally:
        os.chdir(original_dir)

def _verify_project_structure(framework: str) -> None:
    """Verify that the project structure is valid for the detected framework"""
    logger.info(f"Verifying {framework} project structure")
    
    required_files = {
        'angular': ['package.json', 'angular.json', 'src'],
        'react': ['package.json', 'src'],
        'vue': ['package.json', 'src'],
        'nextjs': ['package.json', 'next.config.js']
    }.get(framework, ['package.json'])
    
    missing_files = []
    for file in required_files:
        if not Path(file).exists():
            missing_files.append(file)
    
    if missing_files:
        logger.warning(f"Missing expected files for {framework}: {missing_files}")
    else:
        logger.info(f" Project structure verified for {framework}")

def _install_dependencies(build_strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Install project dependencies with caching and optimization"""
    logger.info(" Installing dependencies")
    
    install_command = build_strategy.get('install_command', 'npm ci --prefer-offline --no-audit --no-fund')
    
    # Check if package-lock.json exists for npm ci
    if 'npm ci' in install_command and not Path('package-lock.json').exists():
        logger.warning("package-lock.json not found, switching to npm install")
        install_command = install_command.replace('npm ci', 'npm install')
    
    # Add performance optimizations
    if 'npm' in install_command and '--prefer-offline' not in install_command:
        install_command += ' --prefer-offline --no-audit --no-fund'
    
    logger.info(f"Running: {install_command}")
    return run_command(install_command)

def _execute_build(build_strategy: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the build command with framework-specific optimizations"""
    logger.info(" Building application")
    
    build_command = build_strategy.get('command', 'npm run build')
    build_type = build_strategy.get('type', 'generic')
    
    # Add framework-specific optimizations
    if build_type == 'angular':
        # Ensure production build
        if 'build:prod' not in build_command and '--prod' not in build_command:
            if 'ng build' in build_command:
                build_command += ' --configuration production'
    
    elif build_type == 'react':
        # Set production environment
        env_vars = {'NODE_ENV': 'production', 'CI': 'true'}
        for key, value in env_vars.items():
            os.environ[key] = value
    
    logger.info(f"Running: {build_command}")
    return run_command(build_command)

def _verify_build_artifacts(build_strategy: Dict[str, Any], app_name: str, framework: str) -> Dict[str, Any]:
    """Verify and catalog build artifacts"""
    logger.info("Verifying build artifacts")
    
    # Determine possible output directories
    output_dir = build_strategy.get('output_dir', 'dist')
    
    possible_dirs = []
    if framework == 'angular':
        possible_dirs = [f"dist/{app_name}", "dist", f"dist/{app_name}-app"]
    elif framework == 'react':
        possible_dirs = ["build", "dist"]
    elif framework == 'vue':
        possible_dirs = ["dist", "build"]
    else:
        possible_dirs = [output_dir, "dist", "build", "public"]
    
    # Find actual build directory
    actual_output_dir = None
    for dir_path in possible_dirs:
        full_path = Path(dir_path)
        if full_path.exists() and _contains_web_artifacts(full_path):
            actual_output_dir = str(full_path)
            logger.info(f" Found build artifacts in: {actual_output_dir}")
            break
    
    if not actual_output_dir:
        raise Exception(f"No build artifacts found in any of: {possible_dirs}")
    
    # Catalog artifacts
    artifacts = []
    total_size = 0
    
    for file_path in Path(actual_output_dir).rglob('*'):
        if file_path.is_file():
            file_size = file_path.stat().st_size
            artifacts.append({
                'path': str(file_path.relative_to(actual_output_dir)),
                'size': file_size
            })
            total_size += file_size
    
    logger.info(f" Build artifacts summary:")
    logger.info(f"   Directory: {actual_output_dir}")
    logger.info(f"   Files: {len(artifacts)}")
    logger.info(f"   Total size: {_format_size(total_size)}")
    
    return {
        'output_dir': actual_output_dir,
        'file_count': len(artifacts),
        'total_size': total_size,
        'files': artifacts
    }

def _contains_web_artifacts(directory: Path) -> bool:
    """Check if directory contains web application artifacts"""
    if not directory.exists() or not any(directory.iterdir()):
        return False
    
    # Look for typical web artifacts
    web_files = list(directory.rglob('*.html')) + list(directory.rglob('*.js')) + list(directory.rglob('*.css'))
    return len(web_files) > 0

def _optimize_artifacts(artifacts_info: Dict[str, Any], framework: str) -> None:
    """Optimize build artifacts if needed"""
    logger.info(" Optimizing build artifacts")
    
    output_dir = Path(artifacts_info['output_dir'])
    
    # Framework-specific optimizations
    if framework == 'angular':
        # Check for source maps in production
        source_maps = list(output_dir.rglob('*.map'))
        if source_maps:
            logger.warning(f"Found {len(source_maps)} source map files - consider disabling in production")
    
    elif framework == 'react':
        # Check for development files
        dev_files = [f for f in artifacts_info['files'] if 'development' in f['path']]
        if dev_files:
            logger.warning(f"Found {len(dev_files)} development files in build")
    
    logger.info("Artifact optimization completed")

def _format_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"