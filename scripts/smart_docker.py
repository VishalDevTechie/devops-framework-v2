# Smart Docker Module - scripts/smart_docker.py

import os
import time
from pathlib import Path
from typing import Dict, Any
from jinja2 import Template
from utils.logger import get_logger
from utils.helpers import run_command

logger = get_logger(__name__)

def run(config: Dict[str, Any], repo_path: str) -> Dict[str, Any]:
    """Smart Docker build and push with framework-specific optimization"""
    logger.info(" Starting Smart Docker Process")
    start_time = time.time()
    
    app_name = config['app']['name']
    framework = config['app']['framework']
    docker_config = config['docker']
    
    logger.info(f"Building Docker image for {app_name} ({framework})")
    
    # Change to repository directory
    original_dir = os.getcwd()
    os.chdir(repo_path)
    
    try:
        # Step 1: Generate or use Dockerfile
        dockerfile_path = _prepare_dockerfile(config, framework, repo_path)
        
        # Step 2: Build Docker image
        image_info = _build_docker_image(docker_config, dockerfile_path)
        
        # Step 3: Tag images
        _tag_docker_images(docker_config)
        
        # Step 4: Push images
        push_results = _push_docker_images(docker_config)
        
        end_time = time.time()
        duration = end_time - start_time
        
        logger.info(f" Smart Docker process completed in {duration:.2f}s")
        
        return {
            'success': True,
            'duration': duration,
            'image_info': image_info,
            'push_results': push_results,
            'dockerfile_path': dockerfile_path
        }
        
    finally:
        os.chdir(original_dir)

def _prepare_dockerfile(config: Dict[str, Any], framework: str, repo_path: str) -> str:
    """Generate or validate Dockerfile for the application"""
    logger.info(" Preparing Dockerfile")
    
    dockerfile_path = Path(repo_path) / "Dockerfile"
    
    # Check if custom Dockerfile exists
    if dockerfile_path.exists():
        logger.info(" Using existing Dockerfile")
        return str(dockerfile_path)
    
    # Generate Dockerfile from template
    logger.info(f"🔧 Generating Dockerfile for {framework}")
    
    template_path = Path("framework/templates/dockerfile") / f"{framework}.dockerfile.j2"
    if not template_path.exists():
        template_path = Path("framework/templates/dockerfile") / "generic.dockerfile.j2"
    
    if not template_path.exists():
        # Create inline template as fallback
        dockerfile_content = _generate_inline_dockerfile(config, framework)
    else:
        with open(template_path) as f:
            template = Template(f.read())
        
        dockerfile_content = template.render(
            app_name=config['app']['name'],
            framework=framework,
            node_version=config.get('build', {}).get('node_version', '18'),
            build_dir=config.get('build_info', {}).get('output_dir', 'dist'),
            port=config['docker'].get('port', 8080)
        )
    
    # Write generated Dockerfile
    with open(dockerfile_path, 'w') as f:
        f.write(dockerfile_content)
    
    logger.info(f" Generated Dockerfile: {dockerfile_path}")
    return str(dockerfile_path)

def _generate_inline_dockerfile(config: Dict[str, Any], framework: str) -> str:
    """Generate inline Dockerfile when template is not available"""
    build_dir = config.get('build_info', {}).get('output_dir', 'dist')
    port = config['docker'].get('port', 8080)
    node_version = config.get('build', {}).get('node_version', '18')
    
    if framework == 'angular':
        return f"""# Multi-stage build for Angular application
FROM node:{node_version}-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --no-fund
COPY . .
RUN npm run build:prod 2>/dev/null || npm run build

# Production stage
FROM nginx:alpine
RUN rm -rf /usr/share/nginx/html/*
COPY --from=build /app/{build_dir} /usr/share/nginx/html

# Custom nginx config for Angular routing
RUN echo 'server {{ \
    listen {port}; \
    location / {{ \
        root /usr/share/nginx/html; \
        index index.html index.htm; \
        try_files \\$uri \\$uri/ /index.html; \
    }} \
}}' > /etc/nginx/conf.d/default.conf

EXPOSE {port}
CMD ["nginx", "-g", "daemon off;"]
"""
    else:
        return f"""# Multi-stage build for {framework} application
FROM node:{node_version}-alpine as build

WORKDIR /app
COPY package*.json ./
RUN npm ci --prefer-offline --no-audit --no-fund
COPY . .
RUN npm run build

# Production stage  
FROM nginx:alpine
COPY --from=build /app/{build_dir} /usr/share/nginx/html
EXPOSE {port}
CMD ["nginx", "-g", "daemon off;"]
"""

def _build_docker_image(docker_config: Dict[str, Any], dockerfile_path: str) -> Dict[str, Any]:
    """Build Docker image with optimizations"""
    logger.info(" Building Docker image")
    
    full_image = docker_config['full_image']
    
    build_args = [
        f"docker build",
        f"-t {full_image}",
        f"-f {dockerfile_path}",
        "."
    ]
    
    build_command = " ".join(build_args)
    logger.info(f"Running: {build_command}")
    
    result = run_command(build_command)
    
    if not result['success']:
        logger.error(f"Docker build failed: {result['stderr']}")
        raise Exception(f"Docker build failed: {result['stderr']}")
    
    logger.info(" Docker image built successfully")
    
    # Get image info
    inspect_result = run_command(f"docker inspect {full_image}")
    image_size = "unknown"
    
    if inspect_result['success']:
        try:
            import json
            image_data = json.loads(inspect_result['stdout'])
            if image_data:
                image_size = image_data[0].get('Size', 'unknown')
        except:
            pass
    
    return {
        'image': full_image,
        'size': image_size,
        'build_output': result['stdout']
    }

def _tag_docker_images(docker_config: Dict[str, Any]) -> None:
    """Tag Docker images (latest, etc.)"""
    logger.info(" Tagging Docker images")
    
    full_image = docker_config['full_image']
    latest_image = docker_config['latest_image']
    
    tag_result = run_command(f"docker tag {full_image} {latest_image}")
    
    if not tag_result['success']:
        logger.warning(f"Failed to tag latest image: {tag_result['stderr']}")
    else:
        logger.info(f"Tagged as latest: {latest_image}")

def _push_docker_images(docker_config: Dict[str, Any]) -> Dict[str, Any]:
    """Push Docker images to registry"""
    logger.info(" Pushing Docker images")
    
    full_image = docker_config['full_image']
    latest_image = docker_config['latest_image']
    
    push_results = {}
    
    # Push versioned image
    logger.info(f"Pushing: {full_image}")
    version_result = run_command(f"docker push {full_image}")
    push_results['versioned'] = version_result
    
    if not version_result['success']:
        raise Exception(f"Failed to push {full_image}: {version_result['stderr']}")
    
    # Push latest image
    logger.info(f"Pushing: {latest_image}")
    latest_result = run_command(f"docker push {latest_image}")
    push_results['latest'] = latest_result
    
    if not latest_result['success']:
        logger.warning(f"Failed to push latest image: {latest_result['stderr']}")
    
    logger.info(" Docker images pushed successfully")
    return push_results