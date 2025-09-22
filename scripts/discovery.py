# scripts/discovery.py
"""
Repository discovery and analysis utilities
Minimal implementation for current iteration
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional
from utils.logger import get_logger

logger = get_logger(__name__)

def discover_repository_structure(repo_path: str) -> Dict[str, Any]:
    """Discover basic repository structure and characteristics"""
    logger.info(f" Discovering repository structure: {repo_path}")
    
    if not Path(repo_path).exists():
        raise Exception(f"Repository path does not exist: {repo_path}")
    
    structure = {
        'root_path': repo_path,
        'files': [],
        'directories': [],
        'config_files': {},
        'source_directories': [],
        'build_artifacts': []
    }
    
    # Scan repository
    for item in Path(repo_path).rglob('*'):
        if item.is_file():
            relative_path = str(item.relative_to(repo_path))
            structure['files'].append(relative_path)
            
            # Check for important config files
            if item.name in ['package.json', 'angular.json', 'tsconfig.json', 'Dockerfile']:
                structure['config_files'][item.name] = str(item)
        
        elif item.is_dir() and not item.name.startswith('.'):
            relative_path = str(item.relative_to(repo_path))
            structure['directories'].append(relative_path)
            
            # Identify source directories
            if item.name in ['src', 'app', 'components', 'pages']:
                structure['source_directories'].append(relative_path)
    
    logger.info(f" Repository structure discovered: {len(structure['files'])} files, {len(structure['directories'])} directories")
    return structure

def analyze_package_json(repo_path: str) -> Optional[Dict[str, Any]]:
    """Analyze package.json for dependencies and scripts"""
    package_path = Path(repo_path) / 'package.json'
    
    if not package_path.exists():
        logger.warning("No package.json found")
        return None
    
    try:
        with open(package_path, 'r') as f:
            package_data = json.load(f)
        
        analysis = {
            'name': package_data.get('name', 'unknown'),
            'version': package_data.get('version', '1.0.0'),
            'dependencies': list(package_data.get('dependencies', {}).keys()),
            'dev_dependencies': list(package_data.get('devDependencies', {}).keys()),
            'scripts': list(package_data.get('scripts', {}).keys()),
            'engines': package_data.get('engines', {}),
            'has_build_script': 'build' in package_data.get('scripts', {}),
            'has_start_script': 'start' in package_data.get('scripts', {}),
            'has_test_script': 'test' in package_data.get('scripts', {})
        }
        
        logger.info(f" Package analysis: {analysis['name']}@{analysis['version']}")
        return analysis
        
    except Exception as e:
        logger.error(f"Failed to analyze package.json: {e}")
        return None

def check_build_outputs(repo_path: str) -> List[str]:
    """Check for existing build output directories"""
    possible_outputs = ['dist', 'build', 'out', 'public', 'www']
    existing_outputs = []
    
    for output_dir in possible_outputs:
        output_path = Path(repo_path) / output_dir
        if output_path.exists() and output_path.is_dir():
            # Check if directory has content
            if any(output_path.iterdir()):
                existing_outputs.append(output_dir)
    
    return existing_outputs