#!/usr/bin/env python3
"""
Run Deploy Script
Entry point for Kubernetes manifest generation
Called by Azure DevOps pipeline
"""

import sys
import os
import json
from pathlib import Path

def main():
    print('=' * 60)
    print('Starting Smart Deployment Process')
    print('=' * 60)
    
    # Get analysis results path
    if len(sys.argv) < 2:
        print('ERROR: Analysis results path not provided')
        print('Usage: python run_deploy.py <analysis_results_path>')
        sys.exit(1)
    
    analysis_file = sys.argv[1]
    
    # Setup paths
    current_dir = os.getcwd()
    scripts_dir = os.path.join(current_dir, 'scripts')
    
    print(f'\nCurrent directory: {current_dir}')
    print(f'Analysis results: {analysis_file}')
    
    # Add scripts to Python path
    if os.path.exists(scripts_dir):
        sys.path.insert(0, scripts_dir)
    else:
        print('ERROR: Scripts directory not found')
        sys.exit(1)
    
    try:
        # Import deploy module
        from smart_deploy import run as deploy_run
        
        # Load configuration
        print('\nLoading configuration...')
        with open(analysis_file) as f:
            analysis_result = json.load(f)
        
        if not analysis_result['success']:
            print('ERROR: Cannot deploy - analysis failed')
            sys.exit(1)
        
        config = analysis_result['config']
        
        # Ensure deployment configuration exists
        if 'deployment' not in config:
            config['deployment'] = {
                'namespace': 'default',
                'environment': 'production',
                'replicas': 1
            }
        
        app_name = config['app']['name']
        framework = config['app']['framework']
        docker_image = config['docker']['full_image']
        
        print('Configuration loaded')
        print(f'\nDeployment Details:')
        print(f'  Application: {app_name}')
        print(f'  Framework: {framework}')
        print(f'  Docker Image: {docker_image}')
        print(f'  Environment: {config["deployment"]["environment"]}')
        print(f'  Namespace: {config["deployment"]["namespace"]}')
        
        # Generate manifests
        print('\nGenerating Kubernetes manifests...')
        deploy_result = deploy_run(config)
        
        print('\n' + '=' * 60)
        if deploy_result['success']:
            print('DEPLOYMENT PREPARATION COMPLETED')
            print('=' * 60)
            print(f'\nManifest file: {deploy_result["manifest_path"]}')
            
            # Display manifest preview
            manifest_path = deploy_result['manifest_path']
            if os.path.exists(manifest_path):
                with open(manifest_path, 'r') as f:
                    manifest_content = f.read()
                    print('\nManifest Preview (first 50 lines):')
                    print('-' * 60)
                    lines = manifest_content.split('\n')
                    for i, line in enumerate(lines[:50], 1):
                        print(f'{i:3d} | {line}')
                    if len(lines) > 50:
                        print(f'... ({len(lines) - 50} more lines)')
                    print('-' * 60)
            
            sys.exit(0)
        else:
            print('DEPLOYMENT PREPARATION FAILED')
            print('=' * 60)
            print(f'\nError: {deploy_result.get("error", "Unknown error")}')
            sys.exit(1)
            
    except Exception as e:
        print(f'\nDeploy script error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()