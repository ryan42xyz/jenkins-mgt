#!/usr/bin/env python3

from flask import Flask, render_template, request, jsonify
from jenkins_manager import JenkinsManager, JobInfo
import json

app = Flask(__name__)
jenkins_manager = JenkinsManager()

# Store manager instances for different environments
jenkins_managers = {}

@app.route('/')
def index():
    """Main dashboard page"""
    return render_template('index.html')

@app.route('/api/jobs')
def get_jobs():
    """API endpoint to get all jobs summary"""
    try:
        # Debug: Print current environment information
        current_env = jenkins_manager.get_current_environment_info()
        print(f"[DEBUG] /api/jobs called - Current environment: {current_env['key']} ({current_env['name']}) - URL: {current_env['url']}")
        
        jobs = jenkins_manager.get_all_jobs_summary()
        jobs_data = []
        for job in jobs:
            jobs_data.append({
                'job_name': job.job_name,
                'latest_build_id': job.latest_build_id,
                'latest_success_build_id': job.latest_success_build_id,
                'latest_build_status': job.latest_build_status,
                'latest_build_timestamp': job.latest_build_timestamp,
                'jenkins_url': job.jenkins_url,
                'console_url': job.console_url,
                'replay_url': job.replay_url,
                'parameters_url': job.parameters_url,
                'github_url': job.github_url,
                'jenkinsfile_path': job.jenkinsfile_path,
                'description': job.description,
                'latest_build_parameters': getattr(job, 'latest_build_parameters', 'No parameters'),
                'latest_commit_id': job.latest_commit_id,
                'latest_commit_short': job.latest_commit_short,
                'category': job.category,
                # Folder information
                'folder_name': getattr(job, 'folder_name', ''),
                'folder_description': getattr(job, 'folder_description', ''),
                'folder_icon': getattr(job, 'folder_icon', ''),
                'pipeline_order': getattr(job, 'pipeline_order', 0),
                # Recent builds for job expansion
                'recent_builds': getattr(job, 'recent_builds', [])
            })
        return jsonify(jobs_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_name>')
def get_job_info(job_name):
    """API endpoint to get specific job information (legacy endpoint)"""
    try:
        job_info = jenkins_manager.get_job_info(job_name)
        return jsonify({
            'job_name': job_info.job_name,
            'latest_build_id': job_info.latest_build_id,
            'latest_success_build_id': job_info.latest_success_build_id,
            'latest_build_status': job_info.latest_build_status,
            'latest_build_timestamp': job_info.latest_build_timestamp,
            'jenkins_url': job_info.jenkins_url,
            'console_url': job_info.console_url,
            'replay_url': job_info.replay_url,
            'parameters_url': job_info.parameters_url,
            'github_url': job_info.github_url,
            'jenkinsfile_path': job_info.jenkinsfile_path,
            'description': job_info.description,
            'latest_build_parameters': getattr(job_info, 'latest_build_parameters', 'No parameters'),
            'latest_commit_id': job_info.latest_commit_id,
            'latest_commit_short': job_info.latest_commit_short,
            'category': job_info.category
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_name>/recent-builds')
def get_job_recent_builds(job_name):
    """API endpoint to get recent builds for a specific job"""
    try:
        limit = request.args.get('limit', 10, type=int)
        builds = jenkins_manager.get_recent_builds(job_name, limit)
        return jsonify({
            'job_name': job_name,
            'builds': builds
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/build/<job_name>/<int:build_id>')
def get_build_info(job_name, build_id):
    """API endpoint to get specific build information"""
    try:
        build_info = jenkins_manager.get_specific_build_info(job_name, build_id)
        return jsonify(build_info)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_name>/parameters')
def get_job_parameters(job_name):
    """API endpoint to get job parameter definitions"""
    try:
        parameters = jenkins_manager.get_job_parameters(job_name)
        return jsonify(parameters)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_name>/build', methods=['POST'])
def trigger_build(job_name):
    """API endpoint to trigger build with parameters"""
    try:
        parameters = request.get_json() or {}
        result = jenkins_manager.trigger_build_with_parameters(job_name, parameters)
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/job/<job_name>/build-string', methods=['POST'])
def trigger_build_string(job_name):
    """API endpoint to trigger build with parameter string"""
    try:
        data = request.get_json() or {}
        param_string = data.get('parameters', '')
        environment = data.get('environment')
        
        # Get the appropriate manager
        manager = get_manager_for_environment(environment)
        
        # Parse parameter string into dict
        parameters = manager.parse_parameter_string(param_string)
        
        # Trigger build
        result = manager.trigger_build_with_parameters(job_name, parameters)
        result['parsed_parameters'] = parameters  # Include parsed params in response
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/environments')
def get_environments():
    """API endpoint to get available environments"""
    try:
        environments = jenkins_manager.get_environments()
        current_env = jenkins_manager.get_current_environment_info()
        return jsonify({
            'environments': environments,
            'current': current_env
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/switch-environment', methods=['POST'])
def switch_environment():
    """API endpoint to switch Jenkins environment"""
    try:
        data = request.get_json() or {}
        environment = data.get('environment')
        
        if not environment:
            return jsonify({'error': 'Environment parameter is required'}), 400
        
        # Switch the global manager
        print(f"[DEBUG] Switching to environment: {environment}")
        success = jenkins_manager.switch_environment(environment)
        
        if success:
            # Clear cached managers
            jenkins_managers.clear()
            
            env_info = jenkins_manager.get_current_environment_info()
            print(f"[DEBUG] Successfully switched to: {env_info['key']} ({env_info['name']}) - URL: {env_info['url']}")
            return jsonify({
                'success': True,
                'message': f'Switched to {env_info["name"]}',
                'environment': env_info
            })
        else:
            return jsonify({
                'success': False,
                'error': f'Environment "{environment}" not found'
            }), 404
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

def get_manager_for_environment(environment=None):
    """Get Jenkins manager for specified environment or use global default"""
    if not environment:
        return jenkins_manager
    
    if environment not in jenkins_managers:
        jenkins_managers[environment] = JenkinsManager(environment=environment)
    
    return jenkins_managers[environment]

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000) 