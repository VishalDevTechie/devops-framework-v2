# Smart Deploy Module - scripts/smart_deploy.py

import os
import yaml
from pathlib import Path
from typing import Dict, Any
from jinja2 import Template
from utils.logger import get_logger
from utils.helpers import run_command

logger = get_logger(__name__)

def run(config: Dict[str, Any]) -> Dict[str, Any]:
    """Smart deployment with auto-generated manifests and health checks"""
    logger.info(" Starting Smart Deployment Process")
    
    app_name = config['app']['name']
    framework = config['app']['framework']
    deployment_config = config['deployment']
    
    logger.info(f"Deploying {app_name} ({framework}) to {deployment_config['environment']}")
    
    try:
        # Step 1: Generate Kubernetes manifests
        manifest_path = _generate_k8s_manifests(config)
        
        # Step 2: Validate manifests
        _validate_k8s_manifests(manifest_path)
        
        # Step 3: Apply deployment
        apply_result = _apply_k8s_manifests(manifest_path, deployment_config)
        
        # Step 4: Wait for rollout
        rollout_result = _wait_for_rollout(app_name, deployment_config)
        
        # Step 5: Verify deployment health
        health_check = _verify_deployment_health(app_name, deployment_config)
        
        logger.info(" Smart deployment completed successfully")
        
        return {
            'success': True,
            'manifest_path': manifest_path,
            'apply_result': apply_result,
            'rollout_result': rollout_result,
            'health_check': health_check
        }
        
    except Exception as e:
        logger.error(f"Deployment failed: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def _generate_k8s_manifests(config: Dict[str, Any]) -> str:
    """Generate Kubernetes manifests from templates"""
    logger.info(" Generating Kubernetes manifests")
    
    template_path = Path("framework/templates/k8s/deployment.yaml.j2")
    
    if not template_path.exists():
        # Use inline template
        manifest_content = _generate_inline_k8s_manifest(config)
    else:
        with open(template_path) as f:
            template = Template(f.read())
        manifest_content = template.render(**config)
    
    # Write manifest
    manifest_path = "generated-k8s-manifest.yaml"
    with open(manifest_path, 'w') as f:
        f.write(manifest_content)
    
    logger.info(f" Generated manifest: {manifest_path}")
    return manifest_path

def _generate_inline_k8s_manifest(config: Dict[str, Any]) -> str:
    """Generate inline Kubernetes manifest"""
    app = config['app']
    docker = config['docker']
    deployment = config['deployment']
    
    return f"""apiVersion: apps/v1
kind: Deployment
metadata:
  name: {app['name']}
  namespace: {deployment.get('namespace', 'default')}
  labels:
    app: {app['name']}
    framework: {app['framework']}
    environment: {deployment['environment']}
spec:
  replicas: {deployment['replicas']}
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  selector:
    matchLabels:
      app: {app['name']}
  template:
    metadata:
      labels:
        app: {app['name']}
        framework: {app['framework']}
        environment: {deployment['environment']}
    spec:
      containers:
      - name: {app['name']}
        image: {docker['full_image']}
        ports:
        - containerPort: {docker.get('port', 8080)}
        env:
        - name: ENVIRONMENT
          value: "{deployment['environment']}"
        - name: APP_NAME
          value: "{app['name']}"
        readinessProbe:
          httpGet:
            path: /
            port: {docker.get('port', 8080)}
          initialDelaySeconds: {deployment.get('health_checks', {}).get('readiness', {}).get('initial_delay', 10)}
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: {docker.get('port', 8080)}
          initialDelaySeconds: {deployment.get('health_checks', {}).get('liveness', {}).get('initial_delay', 30)}
          periodSeconds: 30
        resources:
          requests:
            memory: "{deployment.get('resources', {}).get('requests', {}).get('memory', '128Mi')}"
            cpu: "{deployment.get('resources', {}).get('requests', {}).get('cpu', '100m')}"
          limits:
            memory: "{deployment.get('resources', {}).get('limits', {}).get('memory', '256Mi')}"
            cpu: "{deployment.get('resources', {}).get('limits', {}).get('cpu', '200m')}"
---
apiVersion: v1
kind: Service
metadata:
  name: {app['name']}-service
  namespace: {deployment.get('namespace', 'default')}
  labels:
    app: {app['name']}
    framework: {app['framework']}
spec:
  type: {deployment.get('service_type', 'LoadBalancer')}
  ports:
  - port: {deployment.get('service', {}).get('port', 80)}
    targetPort: {docker.get('port', 8080)}
    protocol: TCP
  selector:
    app: {app['name']}
"""

def _validate_k8s_manifests(manifest_path: str) -> None:
    """Validate Kubernetes manifests"""
    logger.info(" Validating Kubernetes manifests")
    
    # Basic YAML validation
    try:
        with open(manifest_path) as f:
            yaml.safe_load_all(f.read())
        logger.info(" YAML syntax validation passed")
    except yaml.YAMLError as e:
        raise Exception(f"Invalid YAML syntax: {e}")

def _apply_k8s_manifests(manifest_path: str, deployment_config: Dict[str, Any]) -> Dict[str, Any]:
    """Apply Kubernetes manifests"""
    logger.info(" Applying Kubernetes manifests")
    
    namespace = deployment_config.get('namespace', 'default')
    
    apply_command = f"kubectl apply -f {manifest_path} --namespace={namespace}"
    result = run_command(apply_command)
    
    if not result['success']:
        raise Exception(f"Failed to apply manifests: {result['stderr']}")
    
    logger.info(" Manifests applied successfully")
    return result

def _wait_for_rollout(app_name: str, deployment_config: Dict[str, Any]) -> Dict[str, Any]:
    """Wait for deployment rollout to complete"""
    logger.info("⏳ Waiting for deployment rollout")
    
    namespace = deployment_config.get('namespace', 'default')
    timeout = deployment_config.get('rollout_timeout', 300)
    
    rollout_command = f"kubectl rollout status deployment/{app_name} --namespace={namespace} --timeout={timeout}s"
    result = run_command(rollout_command)
    
    if not result['success']:
        logger.warning(f"Rollout status check failed: {result['stderr']}")
        # Try to get more information
        _get_deployment_debug_info(app_name, namespace)
    else:
        logger.info(" Deployment rollout completed successfully")
    
    return result

def _get_deployment_debug_info(app_name: str, namespace: str) -> None:
    """Get debugging information for failed deployment"""
    logger.info(" Getting deployment debug information")
    
    # Get deployment description
    desc_result = run_command(f"kubectl describe deployment/{app_name} --namespace={namespace}")
    if desc_result['success']:
        logger.info("Deployment description:")
        logger.info(desc_result['stdout'])
    
    # Get pod status
    pods_result = run_command(f"kubectl get pods -l app={app_name} --namespace={namespace} -o wide")
    if pods_result['success']:
        logger.info("Pod status:")
        logger.info(pods_result['stdout'])

def _verify_deployment_health(app_name: str, deployment_config: Dict[str, Any]) -> Dict[str, Any]:
    """Verify deployment health and readiness"""
    logger.info(" Verifying deployment health")
    
    namespace = deployment_config.get('namespace', 'default')
    
    # Get deployment status
    status_command = f"kubectl get deployment/{app_name} --namespace={namespace} -o json"
    status_result = run_command(status_command)
    
    health_info = {
        'healthy': False,
        'ready_replicas': 0,
        'desired_replicas': deployment_config['replicas'],
        'status': 'unknown'
    }
    
    if status_result['success']:
        try:
            import json
            deployment_data = json.loads(status_result['stdout'])
            status = deployment_data.get('status', {})
            
            health_info.update({
                'ready_replicas': status.get('readyReplicas', 0),
                'available_replicas': status.get('availableReplicas', 0),
                'updated_replicas': status.get('updatedReplicas', 0),
                'conditions': status.get('conditions', [])
            })
            
            # Check if deployment is healthy
            ready = health_info['ready_replicas']
            desired = health_info['desired_replicas']
            health_info['healthy'] = ready == desired and ready > 0
            health_info['status'] = 'healthy' if health_info['healthy'] else 'unhealthy'
            
        except Exception as e:
            logger.warning(f"Failed to parse deployment status: {e}")
    
    # Get service information
    service_command = f"kubectl get service/{app_name}-service --namespace={namespace} -o json"
    service_result = run_command(service_command)
    
    if service_result['success']:
        try:
            import json
            service_data = json.loads(service_result['stdout'])
            service_spec = service_data.get('spec', {})
            service_status = service_data.get('status', {})
            
            health_info['service'] = {
                'type': service_spec.get('type'),
                'ports': service_spec.get('ports', []),
                'external_ip': service_status.get('loadBalancer', {}).get('ingress', [])
            }
        except Exception as e:
            logger.warning(f"Failed to parse service status: {e}")
    
    if health_info['healthy']:
        logger.info(f" Deployment is healthy: {health_info['ready_replicas']}/{health_info['desired_replicas']} replicas ready")
    else:
        logger.warning(f" Deployment health check: {health_info['ready_replicas']}/{health_info['desired_replicas']} replicas ready")
    
    return health_info