#!/usr/bin/env python3
"""
Run Build Script
Entry point for building and containerizing the application
Called by Azure DevOps pipeline
"""

import sys
import os
import json
from pathlib import Path

def main():
    print('=' * 60)
    print('Starting Smart Build Process')
    print('=' * 60)
    
    # Get arguments
    if len(sys.argv) < 3:
        print('ERROR: Missing required arguments')
        print('Usage: python run_build.py <service_repo_path> <analysis_results_path>')
        sys.exit(1)
    
    service_path = sys.argv[1]
    analysis_file = sys.argv[2]
    
    # Setup paths
    current_dir = os.getcwd()
    scripts_dir = os.path.join(current_dir, 'scripts')
    
    print(f'\nCurrent directory: {current_dir}')
    print(f'Service repository: {service_path}')
    print(f'Analysis results: {analysis_file}')
    
    # Add scripts to Python path
    if os.path.exists(scripts_dir):
        sys.path.insert(0, scripts_dir)
    else:
        print('ERROR: Scripts directory not found')
        sys.exit(1)
    
    try:
        # Import required modules
        from smart_orchestrator import SmartOrchestrator
        
        # Load analysis results
        print('\nLoading analysis results...')
        with open(analysis_file) as f:
            analysis_result = json.load(f)
        
        if not analysis_result['success']:
            print('ERROR: Cannot proceed - analysis failed')
            sys.exit(1)
        
        config = analysis_result['config']
        print(f'Configuration loaded for: {config["app"]["name"]}')
        
        # Initialize orchestrator
        print('\nInitializing orchestrator...')
        orchestrator = SmartOrchestrator()
        
        # Verify service repository
        if not os.path.exists(service_path):
            print(f'ERROR: Service repository not found: {service_path}')
            sys.exit(1)
        
        # Execute build and docker stages
        print('\nStarting build and containerization...')
        result = orchestrator.process_repository(service_path, config)
        
        print('\n' + '=' * 60)
        if result['success']:
            print('BUILD AND CONTAINERIZATION COMPLETED')
            print('=' * 60)
            print(f'\nDuration: {result.get("duration", 0):.2f}s')
            print(f'Application: {result.get("app_name")}')
            print(f'Framework: {result.get("framework")}')
            sys.exit(0)
        else:
            print('BUILD FAILED')
            print('=' * 60)
            print(f'\nError: {result.get("error", "Unknown error")}')
            sys.exit(1)
            
    except Exception as e:
        print(f'\nBuild pipeline error: {e}')
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()