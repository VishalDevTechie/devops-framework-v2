#!/usr/bin/env python3
"""
Run Analysis Script
Entry point for framework detection and configuration generation
Called by Azure DevOps pipeline
"""

import sys
import os
import json
from pathlib import Path

def main():
    print('=' * 60)
    print('Starting Smart Framework Analysis')
    print('=' * 60)
    
    # Get service repository path from command line
    if len(sys.argv) < 2:
        print('ERROR: Service repository path not provided')
        print('Usage: python run_analysis.py <service_repo_path>')
        sys.exit(1)
    
    service_path = sys.argv[1]
    
    # Setup paths
    current_dir = os.getcwd()
    scripts_dir = os.path.join(current_dir, 'scripts')
    
    print(f'\nCurrent directory: {current_dir}')
    print(f'Scripts directory: {scripts_dir}')
    print(f'Service repository: {service_path}')
    
    # Add scripts to Python path
    if os.path.exists(scripts_dir):
        sys.path.insert(0, scripts_dir)
        print('Added scripts to Python path')
    else:
        print(f'ERROR: Scripts directory not found: {scripts_dir}')
        sys.exit(1)
    
    # Verify service repository exists
    if not os.path.exists(service_path):
        print(f'ERROR: Service repository not found at: {service_path}')
        sys.exit(1)
    
    try:
        # Import orchestrator
        print('\nImporting SmartOrchestrator...')
        from smart_orchestrator import SmartOrchestrator
        print('SmartOrchestrator imported successfully')
        
        # Initialize and run analysis
        print('\nInitializing orchestrator...')
        orchestrator = SmartOrchestrator()
        
        print(f'\nAnalyzing repository: {service_path}')
        result = orchestrator.analyze_only(service_path)
        
        # Save results
        output_file = 'analysis-results.json'
        with open(output_file, 'w') as f:
            json.dump(result, f, indent=2, default=str)
        print(f'\nResults saved to: {output_file}')
        
        # Display results
        print('\n' + '=' * 60)
        if result['success']:
            print('ANALYSIS COMPLETED SUCCESSFULLY')
            print('=' * 60)
            
            config = result.get('config', {})
            app = config.get('app', {})
            detection = config.get('detection', {})
            build_strategy = config.get('build_strategy', {})
            docker = config.get('docker', {})
            
            print(f'\nApplication Details:')
            print(f'  Name: {app.get("name", "unknown")}')
            print(f'  Framework: {app.get("framework", "unknown")}')
            print(f'  Confidence: {detection.get("confidence", 0):.1%}')
            
            print(f'\nBuild Strategy:')
            print(f'  Command: {build_strategy.get("command", "unknown")}')
            print(f'  Type: {build_strategy.get("type", "unknown")}')
            
            print(f'\nDocker Configuration:')
            print(f'  Image: {docker.get("full_image", "unknown")}')
            print(f'  Port: {docker.get("port", "unknown")}')
            
            print('\n' + '=' * 60)
            sys.exit(0)
        else:
            print('ANALYSIS FAILED')
            print('=' * 60)
            print(f'\nError: {result.get("error", "Unknown error")}')
            sys.exit(1)
            
    except ImportError as e:
        print(f'\nImport Error: {e}')
        if os.path.exists(scripts_dir):
            print('\nAvailable files in scripts directory:')
            for item in os.listdir(scripts_dir):
                print(f'  - {item}')
        sys.exit(1)
        
    except Exception as e:
        print(f'\nUnexpected Error: {e}')
        import traceback
        print('\nFull traceback:')
        traceback.print_exc()
        sys.exit(1)

if __name__ == '__main__':
    main()