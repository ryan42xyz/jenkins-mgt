#!/usr/bin/env python3

import requests
import json
import yaml
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Union
from datetime import datetime
import re
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
from dotenv import load_dotenv

load_dotenv()  # Load .env file if present

@dataclass
class JobInfo:
    """Core job information data model"""
    job_name: str
    latest_build_id: Optional[int] = None
    latest_success_build_id: Optional[int] = None
    latest_build_status: Optional[str] = None
    latest_build_timestamp: Optional[str] = None
    jenkins_url: str = ""
    console_url: str = ""
    replay_url: str = ""
    parameters_url: str = ""
    github_url: str = ""
    jenkinsfile_path: str = ""
    description: str = ""
    latest_build_parameters: str = ""
    latest_commit_id: str = ""
    latest_commit_short: str = ""
    category: str = ""
    folder_name: str = ""
    folder_description: str = ""
    folder_icon: str = ""
    pipeline_order: int = 0
    recent_builds: List[Dict[str, Any]] = field(default_factory=list)  # Store recent 5 builds for job expansion

class JenkinsManager:
    """Simple Jenkins management service for information aggregation"""
    
    def __init__(self, config_file: str = "jobs_config.yaml", environment: str = None):
        """Initialize Jenkins Manager with configuration file and environment
        
        Args:
            config_file: Path to the YAML configuration file
            environment: Environment to use ('current', 'legacy', etc.)
        """
        self.config = self._load_config(config_file)
        self.current_environment = environment or self.config.get('default_environment', 'current')
        self._setup_jenkins_connection()
    
    def _setup_jenkins_connection(self):
        """Setup Jenkins connection based on current environment.

        Credential resolution order (highest priority first):
          1. Environment variables: JENKINS_{ENV}_URL / _USER / _TOKEN
             e.g. JENKINS_CURRENT_URL, JENKINS_LEGACY_TOKEN
          2. jobs_config.yaml jenkins section (optional, can be omitted)
          3. Bare JENKINS_URL / JENKINS_USER / JENKINS_TOKEN env vars
        """
        environments = self.config.get('environments', {})
        env_key = self.current_environment.upper()  # e.g. "CURRENT", "LEGACY"

        if self.current_environment in environments:
            env_config = environments[self.current_environment]
            jenkins_config = env_config.get('jenkins', {})
            self.environment_name = env_config.get('name', f'Environment {self.current_environment}')
        else:
            jenkins_config = self.config.get('jenkins', {})
            self.environment_name = 'Default Environment'

        self.base_url = (
            os.environ.get(f"JENKINS_{env_key}_URL")
            or jenkins_config.get('url')
            or os.environ.get("JENKINS_URL")
            or "http://localhost:8080"
        ).rstrip('/')
        self.username = (
            os.environ.get(f"JENKINS_{env_key}_USER")
            or jenkins_config.get('username')
            or os.environ.get("JENKINS_USER")
            or "admin"
        )
        self.token = (
            os.environ.get(f"JENKINS_{env_key}_TOKEN")
            or jenkins_config.get('token')
            or os.environ.get("JENKINS_TOKEN")
            or ""
        )
        self.auth = (self.username, self.token)
    
    def switch_environment(self, environment: str) -> bool:
        """Switch to a different Jenkins environment
        
        Args:
            environment: Environment key to switch to
            
        Returns:
            True if environment exists and switch was successful
        """
        environments = self.config.get('environments', {})
        if environment in environments:
            self.current_environment = environment
            self._setup_jenkins_connection()
            return True
        return False
    
    def get_environments(self) -> Dict[str, str]:
        """Get available environments
        
        Returns:
            Dict mapping environment keys to display names
        """
        environments = self.config.get('environments', {})
        return {
            key: env.get('name', f'Environment {key}')
            for key, env in environments.items()
        }
    
    def get_current_environment_info(self) -> Dict[str, str]:
        """Get current environment information
        
        Returns:
            Dict with current environment details
        """
        return {
            'key': self.current_environment,
            'name': self.environment_name,
            'url': self.base_url,
            'username': self.username
        }
    
    def _load_config(self, config_file: str) -> Dict:
        """Load configuration from YAML file"""
        try:
            if os.path.exists(config_file):
                with open(config_file, 'r') as f:
                    return yaml.safe_load(f) or {}
            else:
                print(f"Config file {config_file} not found, using defaults")
                return {}
        except Exception as e:
            print(f"Error loading config file {config_file}: {e}")
            return {}
    
    def _make_request(self, url: str, timeout: int = 15, json_response: bool = True) -> tuple[Optional[Any], Optional[str]]:
        """Make authenticated request to Jenkins API with faster timeout
        
        Returns:
            tuple: (response_data, error_message)
        """
        try:
            response = requests.get(url, auth=self.auth, timeout=timeout)
            if response.status_code == 200:
                if json_response:
                    return response.json(), None
                else:
                    return response.text, None
            else:
                error_msg = f"HTTP {response.status_code} for {url}"
                print(f"Request failed: {error_msg}")
                return None, error_msg
        except requests.exceptions.ConnectTimeout as e:
            error_msg = f"Connection timeout to Jenkins server. Please check VPN connection. ({str(e)})"
            print(f"Request error: {error_msg}")
            return None, error_msg
        except requests.exceptions.ConnectionError as e:
            error_msg = f"Cannot connect to Jenkins server. Please check VPN/network connection. ({str(e)})"
            print(f"Request error: {error_msg}")
            return None, error_msg
        except requests.exceptions.Timeout as e:
            error_msg = f"Request timeout. Jenkins server may be slow or unreachable. ({str(e)})"
            print(f"Request error: {error_msg}")
            return None, error_msg
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            print(f"Request error: {error_msg}")
            return None, error_msg
    
    def _make_requests_batch(self, urls: List[str], timeout: int = 15) -> Dict[str, tuple[Optional[Any], Optional[str]]]:
        """Make multiple HTTP requests concurrently for better performance
        
        Returns:
            Dict mapping URL to (response_data, error_message) tuple
        """
        results = {}
        
        with ThreadPoolExecutor(max_workers=min(len(urls), 10)) as executor:
            future_to_url = {}
            
            for url in urls:
                # Determine if this URL expects JSON or XML response
                json_response = not url.endswith('config.xml')
                future = executor.submit(self._make_request, url, timeout, json_response)
                future_to_url[future] = url
            
            for future in as_completed(future_to_url):
                url = future_to_url[future]
                try:
                    result = future.result()
                    results[url] = result
                except Exception as e:
                    error_msg = f"Batch request error for {url}: {e}"
                    print(error_msg)
                    results[url] = (None, error_msg)
        
        return results
    
    def get_recent_builds(self, job_name: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent builds for a specific job
        
        Args:
            job_name: Name of the Jenkins job
            limit: Number of recent builds to return (default 10)
            
        Returns:
            List of build information dictionaries
        """
        job_url = f"{self.base_url}/job/{job_name}/api/json"
        job_data, error = self._make_request(job_url)
        
        if not job_data:
            return [{
                'id': 'ERROR',
                'status': 'FAILED',
                'timestamp': 'N/A',
                'build_url': '',
                'console_url': '',
                'replay_url': '',
                'parameters_url': '',
                'parameters': 'N/A',
                'user': 'Unknown',
                'error': error or "Failed to fetch job data"
            }]
        
        builds = job_data.get('builds', [])
        recent_builds = []
        
        # Get details for the most recent builds (up to limit)
        build_urls = []
        for build in builds[:limit]:
            if build and 'url' in build:
                build_urls.append(f"{build['url']}api/json")
        
        if not build_urls:
            return [{
                'id': 'N/A',
                'status': 'NO_BUILDS',
                'timestamp': 'N/A',
                'build_url': f"{self.base_url}/job/{job_name}/",
                'console_url': '',
                'replay_url': '',
                'parameters_url': '',
                'parameters': 'No builds found',
                'user': 'N/A',
                'error': 'No builds found for this job'
            }]
        
        # Batch fetch build details
        build_batch_results = self._make_requests_batch(build_urls)
        
        for i, url in enumerate(build_urls):
            build_data, build_error = build_batch_results.get(url, (None, None))
            
            if build_data:
                build_id = build_data.get('number', 'Unknown')
                
                # Extract parameters from build actions
                parameters = self._extract_build_parameters(build_data)
                
                # Extract user information
                user = self._extract_build_user(build_data)
                
                # Handle build status - check if build is still running
                result = build_data.get('result')
                building = build_data.get('building', False)
                
                if building:
                    status = 'RUNNING'
                elif result is None or result == '':
                    # Build might have no result yet or be aborted without result
                    status = 'PENDING'
                else:
                    status = result
                
                build_info = {
                    'id': build_id,
                    'status': status,
                    'timestamp': self._format_timestamp(build_data.get('timestamp')),
                    'build_url': f"{self.base_url}/job/{job_name}/{build_id}/",
                    'console_url': f"{self.base_url}/job/{job_name}/{build_id}/console",
                    'replay_url': f"{self.base_url}/job/{job_name}/{build_id}/replay",
                    'parameters_url': f"{self.base_url}/job/{job_name}/{build_id}/parameters",
                    'duration': self._format_duration(build_data.get('duration', 0)),
                    'parameters': parameters,
                    'user': user,
                    'error': None
                }
            else:
                build_info = {
                    'id': f'Build #{i+1}',
                    'status': 'ERROR',
                    'timestamp': 'N/A',
                    'build_url': '',
                    'console_url': '',
                    'replay_url': '',
                    'parameters_url': '',
                    'duration': 'N/A',
                    'parameters': 'Error loading',
                    'user': 'Unknown',
                    'error': build_error or "Failed to fetch build data"
                }
            
            recent_builds.append(build_info)
        
        return recent_builds
    
    def _extract_build_parameters(self, build_data: Dict) -> str:
        """Extract parameters from build data with smart JSON handling
        
        Args:
            build_data: Build JSON data from Jenkins API
            
        Returns:
            Formatted parameters string
        """
        if not build_data or 'actions' not in build_data:
            return 'No parameters'
        
        parameters = []
        
        for action in build_data.get('actions', []):
            if action and action.get('_class') == 'hudson.model.ParametersAction':
                params = action.get('parameters', [])
                for param in params:
                    if param and 'name' in param and 'value' in param:
                        name = param['name']
                        value = param['value']
                        
                        # Smart truncation that preserves JSON structure
                        value_str = str(value)
                        
                        # Don't truncate during parameter extraction - let the frontend handle it
                        # This ensures the full parameter string is available for "more/less" functionality
                        parameters.append(f"{name}={value_str}")
        
        if not parameters:
            return 'No parameters'
        
        return ', '.join(parameters)
    
    def _extract_build_user(self, build_data: Dict) -> str:
        """Extract user information from build data
        
        Args:
            build_data: Build JSON data from Jenkins API
            
        Returns:
            Username who triggered the build
        """
        if not build_data or 'actions' not in build_data:
            return 'Unknown'
        
        # Look for different user information sources in actions
        for action in build_data.get('actions', []):
            if not action:
                continue
            
            # Check for CauseAction which contains user info
            if action.get('_class') == 'hudson.model.CauseAction':
                causes = action.get('causes', [])
                for cause in causes:
                    if cause and cause.get('_class') == 'hudson.model.Cause$UserIdCause':
                        user_id = cause.get('userId')
                        user_name = cause.get('userName')
                        return user_name or user_id or 'Unknown'
                    elif cause and 'userName' in cause:
                        return cause.get('userName', 'Unknown')
                    elif cause and 'userId' in cause:
                        return cause.get('userId', 'Unknown')
            
            # Check for SCMTrigger (automated builds)
            elif action.get('_class') == 'hudson.triggers.SCMTrigger$SCMTriggerCause':
                return 'SCM Trigger'
            
            # Check for TimerTrigger (scheduled builds)
            elif action.get('_class') == 'hudson.triggers.TimerTrigger$TimerTriggerCause':
                return 'Timer Trigger'
            
            # Check for UpstreamCause (triggered by another job)
            elif action.get('_class') == 'hudson.model.Cause$UpstreamCause':
                upstream_project = action.get('upstreamProject', '')
                return f'Upstream: {upstream_project}' if upstream_project else 'Upstream Trigger'
        
        return 'Unknown'
    
    def _format_timestamp(self, timestamp):
        """Format timestamp from milliseconds to readable string"""
        if not timestamp:
            return 'N/A'
        try:
            return datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        except:
            return 'N/A'
    
    def _format_duration(self, duration_ms):
        """Format duration from milliseconds to readable string"""
        if not duration_ms or duration_ms == 0:
            return 'N/A'
        try:
            seconds = duration_ms / 1000
            minutes = seconds / 60
            if minutes < 1:
                return f"{int(seconds)}s"
            elif minutes < 60:
                return f"{int(minutes)}m {int(seconds % 60)}s"
            else:
                hours = minutes / 60
                return f"{int(hours)}h {int(minutes % 60)}m"
        except:
            return 'N/A'

    def get_job_info(self, job_name: str) -> JobInfo:
        """Get comprehensive job information with optimized requests"""
        job_info = JobInfo(job_name=job_name)
        
        # Prepare all URLs we need to fetch
        job_url = f"{self.base_url}/job/{job_name}/api/json"
        config_url = f"{self.base_url}/job/{job_name}/config.xml"
        
        urls_to_fetch = [job_url, config_url]
        
        # Batch fetch job data and config
        batch_results = self._make_requests_batch(urls_to_fetch)
        job_data, job_error = batch_results.get(job_url, (None, None))
        config_data, config_error = batch_results.get(config_url, (None, None))
        
        if not job_data:
            # Store error information in job info for UI display
            error_msg = job_error or "Failed to fetch job data"
            job_info.description = f"⚠️ ERROR: {error_msg}"
            return job_info
        
        # Basic job information
        job_info.description = job_data.get('description', '')
        job_info.jenkins_url = f"{self.base_url}/job/{job_name}/"
        
        # Latest build information
        latest_build = job_data.get('lastBuild')
        build_urls = []
        
        if latest_build:
            job_info.latest_build_id = latest_build.get('number')
            build_urls.append(f"{latest_build['url']}api/json")
        
        # Latest successful build
        last_success = job_data.get('lastSuccessfulBuild')
        if last_success:
            job_info.latest_success_build_id = last_success.get('number')
        
        # Generate URLs
        if job_info.latest_build_id:
            build_id = job_info.latest_build_id
            job_info.console_url = f"{self.base_url}/job/{job_name}/{build_id}/console"
            job_info.replay_url = f"{self.base_url}/job/{job_name}/{build_id}/replay"
            job_info.parameters_url = f"{self.base_url}/job/{job_name}/{build_id}/parameters"
        
        # Fetch build data if needed
        if build_urls:
            build_batch_results = self._make_requests_batch(build_urls)
            build_data, build_error = build_batch_results.get(build_urls[0], (None, None))
            
            if build_data:
                # Check if build is currently running
                if build_data.get('building', False):
                    job_info.latest_build_status = 'RUNNING'
                else:
                    # Build is completed, get the result
                    result = build_data.get('result')
                    if result:
                        job_info.latest_build_status = result
                    else:
                        # Still no result - might be in queue or starting
                        job_info.latest_build_status = 'PENDING'
                
                timestamp = build_data.get('timestamp')
                if timestamp:
                    job_info.latest_build_timestamp = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
                
                # Get commit information from build data
                if 'actions' in build_data:
                    for action in build_data['actions']:
                        if action and action.get('_class') == 'hudson.plugins.git.util.BuildData':
                            last_built_revision = action.get('lastBuiltRevision')
                            if last_built_revision and 'SHA1' in last_built_revision:
                                commit_id = last_built_revision['SHA1']
                                job_info.latest_commit_id = commit_id
                                job_info.latest_commit_short = commit_id[:8] if commit_id else ""
                                break
        
        # Parse Git repository info and Jenkinsfile path from config
        if config_data:
            jenkinsfile_path, git_url, config_branch = self._parse_job_config(config_data)
            job_info.jenkinsfile_path = jenkinsfile_path
            
            # Try to get actual branch from latest build data (more accurate)
            actual_branch = self._get_actual_branch_from_build(build_data, git_url) if build_data else None
            
            # Use actual branch if available, otherwise fall back to config branch
            branch_to_use = actual_branch or config_branch
            job_info.github_url = self._generate_github_url(git_url, branch_to_use, jenkinsfile_path)
        
        # Get recent builds for job expansion functionality
        job_info.recent_builds = self.get_recent_builds(job_name, limit=5)
        
        return job_info
    
    def _parse_job_config(self, config_text: str) -> tuple:
        """Parse job configuration XML to extract Git and Jenkinsfile info"""
        try:
            import xml.etree.ElementTree as ET
            root = ET.fromstring(config_text)
            
            # Get Jenkinsfile path
            script_path_elem = root.find('.//scriptPath')
            jenkinsfile_path = script_path_elem.text if script_path_elem is not None and script_path_elem.text else "Not found"
            
            # Get Git repository URL
            git_url_elem = root.find('.//scm[@class="hudson.plugins.git.GitSCM"]//userRemoteConfigs//hudson.plugins.git.UserRemoteConfig//url')
            git_url = git_url_elem.text if git_url_elem is not None and git_url_elem.text else ""
            
            # Get branch name
            branch_elem = root.find('.//branches//hudson.plugins.git.BranchSpec//name')
            branch = branch_elem.text if branch_elem is not None and branch_elem.text else "master"
            
            # Clean up branch name (remove */prefix if present)
            if branch.startswith('*/'):
                branch = branch[2:]
            
            return jenkinsfile_path, git_url, branch
        except Exception as e:
            print(f"Error parsing job config: {e}")
            return "Not found", "", "master"
    
    def _get_commit_info(self, job_name: str, build_id: int) -> tuple[str, str]:
        """Get Git commit information for a build
        
        Returns:
            tuple: (full_commit_id, short_commit_id)
        """
        if not build_id:
            return "", ""
        
        try:
            url = f"{self.base_url}/job/{job_name}/{build_id}/api/json"
            data, error = self._make_request(url)
            
            if not data or 'actions' not in data:
                return "", ""
            
            # Look for Git build data in actions
            for action in data['actions']:
                if action and action.get('_class') == 'hudson.plugins.git.util.BuildData':
                    # Get the last built revision
                    last_built_revision = action.get('lastBuiltRevision')
                    if last_built_revision and 'SHA1' in last_built_revision:
                        commit_id = last_built_revision['SHA1']
                        commit_short = commit_id[:8] if commit_id else ""
                        return commit_id, commit_short
            
            return "", ""
        except Exception as e:
            print(f"Error getting commit info for {job_name}/{build_id}: {e}")
            return "", ""
    
    def _get_actual_branch_from_build(self, build_data: Dict, target_git_url: str) -> Optional[str]:
        """Extract actual branch used in build from build data
        
        Args:
            build_data: Build JSON data from Jenkins API
            target_git_url: The git URL we're looking for to match the correct repository
            
        Returns:
            Actual branch name used in the build, or None if not found
        """
        if not build_data or 'actions' not in build_data:
            return None
        
        try:
            # Look for Git build data in actions
            for action in build_data.get('actions', []):
                if action and action.get('_class') == 'hudson.plugins.git.util.BuildData':
                    # Check if this is the right repository
                    remote_urls = action.get('remoteUrls', [])
                    
                    # Normalize URLs for comparison (remove .git suffix)
                    normalized_target = target_git_url.rstrip('.git')
                    normalized_remotes = [url.rstrip('.git') for url in remote_urls]
                    
                    if normalized_target in normalized_remotes:
                        # Get the actual branch used in this build
                        last_built_revision = action.get('lastBuiltRevision')
                        if last_built_revision and 'branch' in last_built_revision:
                            branches = last_built_revision['branch']
                            if branches and len(branches) > 0:
                                branch_name = branches[0].get('name', '')
                                # Clean up branch name: refs/remotes/origin/branch -> branch
                                if branch_name.startswith('refs/remotes/origin/'):
                                    return branch_name[len('refs/remotes/origin/'):]
                                elif branch_name.startswith('origin/'):
                                    return branch_name[len('origin/'):]
                                else:
                                    return branch_name
            
            return None
        except Exception as e:
            print(f"Error extracting actual branch from build data: {e}")
            return None
    
    def get_job_parameters(self, job_name: str) -> List[Dict]:
        """Get job parameters definition"""
        job_url = f"{self.base_url}/job/{job_name}/api/json"
        job_data, error = self._make_request(job_url)
        
        if not job_data:
            return []
        
        parameters = []
        property_list = job_data.get('property', [])
        
        for prop in property_list:
            if prop.get('_class') == 'hudson.model.ParametersDefinitionProperty':
                param_definitions = prop.get('parameterDefinitions', [])
                for param_def in param_definitions:
                    param_info = {
                        'name': param_def.get('name', ''),
                        'type': param_def.get('type', 'string'),
                        'defaultValue': param_def.get('defaultParameterValue', {}).get('value', ''),
                        'description': param_def.get('description', ''),
                        'choices': param_def.get('choices', []) if param_def.get('type') == 'choice' else []
                    }
                    parameters.append(param_info)
        
        return parameters
    
    def trigger_build_with_parameters(self, job_name: str, parameters: Dict[str, str]) -> Dict[str, Any]:
        """Trigger a build with parameters"""
        try:
            if parameters:
                # Build with parameters
                build_url = f"{self.base_url}/job/{job_name}/buildWithParameters"
                response = requests.post(build_url, auth=self.auth, data=parameters, timeout=30)
            else:
                # Build without parameters
                build_url = f"{self.base_url}/job/{job_name}/build"
                response = requests.post(build_url, auth=self.auth, timeout=30)
            
            if response.status_code in [200, 201]:
                # Get queue item from Location header or check recent builds
                queue_url = response.headers.get('Location')
                return {
                    'success': True,
                    'message': 'Build triggered successfully',
                    'queue_url': queue_url,
                    'job_url': f"{self.base_url}/job/{job_name}/"
                }
            else:
                return {
                    'success': False,
                    'message': f'Failed to trigger build: HTTP {response.status_code}',
                    'details': response.text[:200]
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error triggering build: {str(e)}'
            }
    
    def parse_parameter_string(self, param_string: str) -> Dict[str, str]:
        """Parse parameter string like 'KEY1=value1, KEY2=value2' into dict with smart JSON handling"""
        parameters = {}
        if not param_string or not param_string.strip():
            return parameters
        
        try:
            print(f"[DEBUG] Parsing parameter string: {param_string}")
            
            # Smart parsing that handles JSON values with commas inside
            pairs = []
            current_pair = ''
            brace_count = 0
            bracket_count = 0
            in_quotes = False
            escape_next = False
            
            for i, char in enumerate(param_string):
                if escape_next:
                    current_pair += char
                    escape_next = False
                    continue
                
                if char == '\\':
                    current_pair += char
                    escape_next = True
                    continue
                
                if char == '"' and not escape_next:
                    in_quotes = not in_quotes
                    current_pair += char
                    continue
                
                if not in_quotes:
                    if char == '{':
                        brace_count += 1
                    elif char == '}':
                        brace_count -= 1
                    elif char == '[':
                        bracket_count += 1
                    elif char == ']':
                        bracket_count -= 1
                    elif char == ',' and brace_count == 0 and bracket_count == 0:
                        # This comma is a parameter separator
                        if current_pair.strip():
                            pairs.append(current_pair.strip())
                        current_pair = ''
                        continue
                
                current_pair += char
            
            # Add the last pair
            if current_pair.strip():
                pairs.append(current_pair.strip())
            
            print(f"[DEBUG] Parsed pairs: {pairs}")
            
            # Parse each key=value pair
            for pair in pairs:
                if '=' in pair:
                    key, value = pair.split('=', 1)  # Split only on first =
                    key = key.strip()
                    value = value.strip()
                    parameters[key] = value
                    print(f"[DEBUG] Added parameter: {key} = {value[:100]}..." if len(value) > 100 else f"[DEBUG] Added parameter: {key} = {value}")
                elif pair.strip():  # Handle keys without values
                    parameters[pair.strip()] = ''
                    print(f"[DEBUG] Added empty parameter: {pair.strip()}")
            
            print(f"[DEBUG] Final parameters: {list(parameters.keys())}")
            return parameters
            
        except Exception as e:
            print(f"[ERROR] Error parsing parameter string '{param_string[:200]}...': {e}")
            return {}
    
    def get_specific_build_info(self, job_name: str, build_id: int) -> Dict[str, str]:
        """Get information for a specific build ID"""
        urls = {
            'console_url': f"{self.base_url}/job/{job_name}/{build_id}/console",
            'replay_url': f"{self.base_url}/job/{job_name}/{build_id}/replay", 
            'parameters_url': f"{self.base_url}/job/{job_name}/{build_id}/parameters",
            'build_url': f"{self.base_url}/job/{job_name}/{build_id}/",
            'api_url': f"{self.base_url}/job/{job_name}/{build_id}/api/json"
        }
        
        # Get build status and info
        build_data, error = self._make_request(urls['api_url'])
        if build_data:
            urls['status'] = build_data.get('result', 'UNKNOWN')
            timestamp = build_data.get('timestamp')
            if timestamp:
                urls['timestamp'] = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
            
            # Get parameters if available
            actions = build_data.get('actions', [])
            parameters = []
            for action in actions:
                if action.get('_class') == 'hudson.model.ParametersAction':
                    params = action.get('parameters', [])
                    for param in params:
                        parameters.append(f"{param.get('name', '')}={param.get('value', '')}")
            urls['parameters'] = ', '.join(parameters) if parameters else 'No parameters'
        
        return urls
    
    def _get_git_and_jenkinsfile_info(self, job_name: str) -> tuple:
        """Get Git repository info and Jenkinsfile path from job configuration"""
        config_url = f"{self.base_url}/job/{job_name}/config.xml"
        try:
            response = requests.get(config_url, auth=self.auth, timeout=30)
            if response.status_code == 200:
                import xml.etree.ElementTree as ET
                root = ET.fromstring(response.text)
                
                # Get Jenkinsfile path
                script_path_elem = root.find('.//scriptPath')
                jenkinsfile_path = script_path_elem.text if script_path_elem is not None and script_path_elem.text else "Not found"
                
                # Get Git repository URL
                git_url_elem = root.find('.//scm[@class="hudson.plugins.git.GitSCM"]//userRemoteConfigs//hudson.plugins.git.UserRemoteConfig//url')
                git_url = git_url_elem.text if git_url_elem is not None and git_url_elem.text else ""
                
                # Get branch name
                branch_elem = root.find('.//branches//hudson.plugins.git.BranchSpec//name')
                branch = branch_elem.text if branch_elem is not None and branch_elem.text else "master"
                
                # Clean up branch name (remove */prefix if present)
                if branch.startswith('*/'):
                    branch = branch[2:]
                
                return jenkinsfile_path, git_url, branch
                
        except Exception as e:
            print(f"Error parsing config for {job_name}: {e}")
        
        return "Not found", "", "master"
    
    def _generate_github_url(self, git_url: str, branch: str, jenkinsfile_path: str) -> str:
        """Generate GitHub URL for Jenkinsfile"""
        if not git_url or not jenkinsfile_path or jenkinsfile_path == "Not found":
            return ""
        
        try:
            # Convert Git URL to GitHub blob URL
            # From: https://github.com/datavisorcode/jenkins-config.git
            # To: https://github.com/datavisorcode/jenkins-config/blob/branch/path
            if git_url.endswith('.git'):
                git_url = git_url[:-4]  # Remove .git suffix
            
            github_url = f"{git_url}/blob/{branch}/{jenkinsfile_path}"
            return github_url
            
        except Exception as e:
            print(f"Error generating GitHub URL: {e}")
            return ""
    
    def get_all_jobs_summary(self) -> List[JobInfo]:
        """Get summary of all configured jobs with concurrent processing, supporting both folder and flat structure"""
        start_time = time.time()
        
        # Try folder structure first
        folders_config = self.config.get('folders', [])
        if folders_config:
            print("Using folder structure from config")
            return self._get_jobs_from_folders(folders_config)
        
        # Fallback to legacy flat structure
        jobs_config = self.config.get('jobs', [])
        
        if not jobs_config:
            print("No jobs found in config, falling back to job.md")
            # Fallback to job.md for backward compatibility
            job_names = []
            try:
                with open('job.md', 'r') as f:
                    for line in f:
                        line = line.strip()
                        if line and line.startswith('http'):
                            # Extract job name from URL
                            job_url = line.split('#')[0].strip()
                            from urllib.parse import urlparse, unquote
                            path = urlparse(job_url).path.rstrip('/')
                            parts = path.split('/')
                            try:
                                job_index = parts.index('job')
                                if job_index + 1 < len(parts):
                                    job_name = unquote(parts[job_index + 1])
                                    job_names.append((job_name, "", ""))  # (name, description, category)
                            except ValueError:
                                continue
            except FileNotFoundError:
                print("job.md not found, using API to get jobs")
                # Final fallback to API
                api_data, error = self._make_request(f"{self.base_url}/api/json")
                if api_data and 'jobs' in api_data:
                    job_names = [(job['name'], "", "") for job in api_data['jobs']]
                elif error:
                    # Return error for UI display
                    return [JobInfo(
                        job_name="CONNECTION_ERROR",
                        description=f"⚠️ NETWORK ERROR: {error}",
                        category="error"
                    )]
        else:
            # Extract job info from config
            job_names = [(job.get('name', ''), job.get('description', ''), job.get('category', '')) 
                        for job in jobs_config if job.get('name')]
        
        print(f"Using legacy flat structure. Fetching info for {len(job_names)} jobs concurrently...")
        
        # Use ThreadPoolExecutor for concurrent job info fetching
        jobs_info = []
        with ThreadPoolExecutor(max_workers=min(len(job_names), 8)) as executor:
            # Submit all job info fetch tasks
            future_to_job = {
                executor.submit(self._get_job_info_with_metadata, job_name, config_description, category): 
                (job_name, config_description, category)
                for job_name, config_description, category in job_names
            }
            
            # Collect results as they complete
            for future in as_completed(future_to_job):
                job_name, config_description, category = future_to_job[future]
                try:
                    job_info = future.result()
                    if job_info:
                        jobs_info.append(job_info)
                        print(f"✓ Completed: {job_name}")
                except Exception as e:
                    print(f"✗ Error fetching {job_name}: {e}")
                    # Create a basic job info for failed requests
                    job_info = JobInfo(
                        job_name=job_name,
                        description=config_description or f"Error: {str(e)}",
                        category=category
                    )
                    jobs_info.append(job_info)
        
        # Sort jobs by name to maintain consistent order
        jobs_info.sort(key=lambda x: x.job_name)
        
        elapsed_time = time.time() - start_time
        print(f"Fetched {len(jobs_info)} jobs in {elapsed_time:.2f} seconds")
        
        return jobs_info
    
    def _get_jobs_from_folders(self, folders_config: List[Dict]) -> List[JobInfo]:
        """Get jobs from folder structure, maintaining pipeline order"""
        start_time = time.time()
        
        # Sort folders by order
        sorted_folders = sorted(folders_config, key=lambda f: f.get('order', 999))
        
        all_job_tasks = []
        folder_info_map = {}
        
        # Collect all jobs from all folders with their metadata
        for folder in sorted_folders:
            folder_name = folder.get('name', 'Unknown Folder')
            folder_description = folder.get('description', '')
            folder_icon = folder.get('icon', 'fas fa-folder')
            
            pipelines = folder.get('pipelines', [])
            # Sort pipelines by order within each folder
            sorted_pipelines = sorted(pipelines, key=lambda p: p.get('order', 999))
            
            for pipeline in sorted_pipelines:
                job_name = pipeline.get('name', '')
                if job_name:
                    # Store folder info for this job
                    folder_info_map[job_name] = {
                        'folder_name': folder_name,
                        'folder_description': folder_description,
                        'folder_icon': folder_icon,
                        'pipeline_order': pipeline.get('order', 999),
                        'description': pipeline.get('description', ''),
                        'category': folder_name.lower().replace(' ', '-')
                    }
                    all_job_tasks.append(job_name)
        
        print(f"Fetching info for {len(all_job_tasks)} jobs from {len(sorted_folders)} folders concurrently...")
        
        # Use ThreadPoolExecutor for concurrent job info fetching
        jobs_info = []
        with ThreadPoolExecutor(max_workers=min(len(all_job_tasks), 8)) as executor:
            # Submit all job info fetch tasks
            future_to_job = {}
            for job_name in all_job_tasks:
                folder_info = folder_info_map[job_name]
                future = executor.submit(
                    self._get_job_info_with_folder_metadata, 
                    job_name, 
                    folder_info
                )
                future_to_job[future] = job_name
            
            # Collect results as they complete
            for future in as_completed(future_to_job):
                job_name = future_to_job[future]
                try:
                    job_info = future.result()
                    if job_info:
                        jobs_info.append(job_info)
                        print(f"✓ Completed: {job_info.folder_name} -> {job_name}")
                except Exception as e:
                    print(f"✗ Error fetching {job_name}: {e}")
                    # Create a basic job info for failed requests
                    folder_info = folder_info_map.get(job_name, {})
                    job_info = JobInfo(
                        job_name=job_name,
                        description=f"Error: {str(e)}",
                        category=folder_info.get('category', 'error'),
                        folder_name=folder_info.get('folder_name', 'Unknown'),
                        folder_description=folder_info.get('folder_description', ''),
                        folder_icon=folder_info.get('folder_icon', 'fas fa-exclamation-triangle'),
                        pipeline_order=folder_info.get('pipeline_order', 999)
                    )
                    jobs_info.append(job_info)
        
        # Sort jobs by folder order, then by pipeline order within each folder
        jobs_info.sort(key=lambda x: (
            next((i for i, f in enumerate(sorted_folders) if f.get('name') == x.folder_name), 999),
            x.pipeline_order,
            x.job_name
        ))
        
        elapsed_time = time.time() - start_time
        print(f"Fetched {len(jobs_info)} jobs from folders in {elapsed_time:.2f} seconds")
        
        return jobs_info
    
    def _get_job_info_with_metadata(self, job_name: str, config_description: str, category: str) -> Optional[JobInfo]:
        """Get job info with additional metadata (used for concurrent processing)"""
        try:
            job_info = self.get_job_info(job_name)
            
            # Override description if provided in config
            if config_description:
                job_info.description = config_description
            
            # Set category from config
            job_info.category = category
            
            # Get latest build parameters for display
            if job_info.latest_build_id:
                build_info = self.get_specific_build_info(job_name, job_info.latest_build_id)
                job_info.latest_build_parameters = build_info.get('parameters', 'No parameters')
            else:
                job_info.latest_build_parameters = 'No builds'
                
            return job_info
        except Exception as e:
            print(f"Error processing job {job_name}: {e}")
            return None
    
    def _get_job_info_with_folder_metadata(self, job_name: str, folder_info: Dict) -> Optional[JobInfo]:
        """Get job info with folder metadata (used for folder structure processing)"""
        try:
            job_info = self.get_job_info(job_name)
            
            # Set folder metadata
            job_info.folder_name = folder_info.get('folder_name', '')
            job_info.folder_description = folder_info.get('folder_description', '')
            job_info.folder_icon = folder_info.get('folder_icon', 'fas fa-folder')
            job_info.pipeline_order = folder_info.get('pipeline_order', 999)
            
            # Override description if provided in config
            if folder_info.get('description'):
                job_info.description = folder_info['description']
            
            # Set category from folder
            job_info.category = folder_info.get('category', 'folder')
            
            # Get latest build parameters for display
            if job_info.latest_build_id:
                build_info = self.get_specific_build_info(job_name, job_info.latest_build_id)
                job_info.latest_build_parameters = build_info.get('parameters', 'No parameters')
            else:
                job_info.latest_build_parameters = 'No builds'
                
            return job_info
        except Exception as e:
            print(f"Error processing job {job_name}: {e}")
            return None

def main():
    """Test the Jenkins manager"""
    manager = JenkinsManager()
    
    # Test with a specific job
    job_name = "global-entrypoint"
    print(f"Testing with job: {job_name}")
    
    job_info = manager.get_job_info(job_name)
    print(f"Job: {job_info.job_name}")
    print(f"Latest Build: {job_info.latest_build_id}")
    print(f"Latest Success: {job_info.latest_success_build_id}")
    print(f"Status: {job_info.latest_build_status}")
    print(f"Console URL: {job_info.console_url}")
    print(f"Replay URL: {job_info.replay_url}")
    print(f"Jenkinsfile: {job_info.jenkinsfile_path}")
    print(f"GitHub URL: {job_info.github_url}")

if __name__ == "__main__":
    main() 