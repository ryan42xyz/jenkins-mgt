#!/usr/bin/env python3

import unittest
from unittest.mock import Mock, patch, MagicMock
import json
import yaml
from dataclasses import asdict
import sys
import os

# Add the current directory to the path so we can import jenkins_manager
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jenkins_manager import JenkinsManager, JobInfo


class TestJenkinsManager(unittest.TestCase):
    """Unit tests for JenkinsManager class"""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Isolate tests from any local .env / shell environment
        self.env_patcher = patch.dict(os.environ, {
            'JENKINS_CURRENT_URL': '', 'JENKINS_CURRENT_USER': '', 'JENKINS_CURRENT_TOKEN': '',
            'JENKINS_LEGACY_URL': '',  'JENKINS_LEGACY_USER': '',  'JENKINS_LEGACY_TOKEN': '',
            'JENKINS_URL': '',         'JENKINS_USER': '',          'JENKINS_TOKEN': '',
        })
        self.env_patcher.start()

        self.test_config = {
            'environments': {
                'current': {
                    'name': 'Test Environment',
                    'jenkins': {
                        'url': 'http://test-jenkins.com',
                        'username': 'testuser',
                        'token': 'testtoken'
                    }
                }
            },
            'default_environment': 'current',
            'folders': [
                {
                    'name': 'Test Folder',
                    'description': 'Test folder description',
                    'icon': 'fas fa-test',
                    'order': 1,
                    'pipelines': [
                        {
                            'name': 'test-job',
                            'description': 'Test job description',
                            'order': 1
                        }
                    ]
                }
            ],
            'jobs': [
                {
                    'name': 'test-job',
                    'description': 'Test job description',
                    'category': 'test'
                }
            ]
        }
        
    def tearDown(self):
        self.env_patcher.stop()

    @patch('jenkins_manager.os.path.exists')
    @patch('builtins.open')
    @patch('yaml.safe_load')
    def test_load_config_success(self, mock_yaml_load, mock_open, mock_exists):
        """Test successful configuration loading"""
        mock_exists.return_value = True
        mock_yaml_load.return_value = self.test_config
        
        manager = JenkinsManager('test_config.yaml')
        
        self.assertEqual(manager.base_url, 'http://test-jenkins.com')
        self.assertEqual(manager.username, 'testuser')
        self.assertEqual(manager.token, 'testtoken')
        
    @patch('jenkins_manager.os.path.exists')
    def test_load_config_file_not_found(self, mock_exists):
        """Test configuration loading when file doesn't exist"""
        mock_exists.return_value = False
        
        manager = JenkinsManager('nonexistent_config.yaml')
        
        # Should fall back to defaults
        self.assertEqual(manager.base_url, 'http://localhost:8080')
        
    def test_switch_environment(self):
        """Test environment switching functionality"""
        with patch('jenkins_manager.os.path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('yaml.safe_load', return_value=self.test_config):
            
            manager = JenkinsManager()
            
            # Test switching to existing environment
            result = manager.switch_environment('current')
            self.assertTrue(result)
            
            # Test switching to non-existent environment
            result = manager.switch_environment('nonexistent')
            self.assertFalse(result)
            
    def test_get_environments(self):
        """Test getting available environments"""
        with patch('jenkins_manager.os.path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('yaml.safe_load', return_value=self.test_config):
            
            manager = JenkinsManager()
            environments = manager.get_environments()
            
            self.assertIn('current', environments)
            self.assertEqual(environments['current'], 'Test Environment')
            
    @patch('requests.get')
    def test_make_request_success(self, mock_get):
        """Test successful API request"""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'test': 'data'}
        mock_get.return_value = mock_response
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            data, error = manager._make_request('http://test.com/api')
            
            self.assertEqual(data, {'test': 'data'})
            self.assertIsNone(error)
            
    @patch('requests.get')
    def test_make_request_failure(self, mock_get):
        """Test failed API request"""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            data, error = manager._make_request('http://test.com/api')
            
            self.assertIsNone(data)
            self.assertIsNotNone(error)
            
    @patch('requests.get')
    def test_make_request_timeout(self, mock_get):
        """Test API request timeout"""
        mock_get.side_effect = Exception("Connection timeout")
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            data, error = manager._make_request('http://test.com/api')
            
            self.assertIsNone(data)
            self.assertIn("Connection timeout", error)
            
    @patch.object(JenkinsManager, '_make_request')
    def test_get_recent_builds_success(self, mock_request):
        """Test getting recent builds successfully"""
        mock_job_data = {
            'builds': [
                {'number': 123, 'url': 'http://test.com/job/test/123/'},
                {'number': 122, 'url': 'http://test.com/job/test/122/'}
            ]
        }
        
        mock_build_data = {
            'number': 123,
            'result': 'SUCCESS',
            'timestamp': 1640995200000,  # 2022-01-01 00:00:00
            'duration': 120000,  # 2 minutes
            'actions': [
                {
                    'causes': [{'userName': 'testuser'}]
                }
            ]
        }
        
        # Mock multiple requests - job data and build data
        mock_request.side_effect = [
            (mock_job_data, None),  # Job data
            (mock_build_data, None),  # First build data
            (mock_build_data, None)   # Second build data
        ]
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            builds = manager.get_recent_builds('test-job', limit=2)
            
            self.assertEqual(len(builds), 2)
            self.assertEqual(builds[0]['id'], 123)
            self.assertEqual(builds[0]['status'], 'SUCCESS')
            
    @patch.object(JenkinsManager, '_make_request')
    def test_get_recent_builds_error(self, mock_request):
        """Test getting recent builds with error"""
        mock_request.return_value = (None, "Connection failed")
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            builds = manager.get_recent_builds('test-job')
            
            self.assertEqual(len(builds), 1)
            self.assertEqual(builds[0]['id'], 'ERROR')
            self.assertEqual(builds[0]['status'], 'FAILED')
            
    def test_extract_build_parameters(self):
        """Test parameter extraction from build data"""
        build_data = {
            'actions': [
                {
                    '_class': 'hudson.model.ParametersAction',
                    'parameters': [
                        {'name': 'SERVICE_NAME', 'value': 'admin-ui'},
                        {'name': 'BRANCH', 'value': 'main'}
                    ]
                }
            ]
        }
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            params = manager._extract_build_parameters(build_data)
            
            self.assertIn('SERVICE_NAME=admin-ui', params)
            self.assertIn('BRANCH=main', params)
            
    def test_extract_build_user(self):
        """Test user extraction from build data"""
        build_data = {
            'actions': [
                {
                    '_class': 'hudson.model.CauseAction',
                    'causes': [
                        {
                            '_class': 'hudson.model.Cause$UserIdCause',
                            'userName': 'testuser',
                            'userId': 'testuser'
                        }
                    ]
                }
            ]
        }
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            user = manager._extract_build_user(build_data)
            
            self.assertEqual(user, 'testuser')
            
    def test_format_timestamp(self):
        """Test timestamp formatting"""
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            
            # Test valid timestamp
            formatted = manager._format_timestamp(1640995200000)  # 2022-01-01 00:00:00
            self.assertIsInstance(formatted, str)
            self.assertIn('2022', formatted)
            
            # Test None timestamp
            formatted = manager._format_timestamp(None)
            self.assertEqual(formatted, 'N/A')
            
    def test_format_duration(self):
        """Test duration formatting"""
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            
            # Test various durations
            self.assertEqual(manager._format_duration(120000), '2m 0s')  # 2 minutes
            self.assertEqual(manager._format_duration(65000), '1m 5s')   # 1 minute 5 seconds
            self.assertEqual(manager._format_duration(30000), '30s')     # 30 seconds
            self.assertEqual(manager._format_duration(None), 'N/A')
            
    @patch.object(JenkinsManager, 'get_recent_builds')
    @patch.object(JenkinsManager, '_make_requests_batch')
    def test_get_job_info(self, mock_batch, mock_recent_builds):
        """Test getting job information"""
        mock_job_data = {
            'description': 'Test job',
            'lastBuild': {'number': 123, 'url': 'http://test.com/job/test/123/'},
            'lastSuccessfulBuild': {'number': 122}
        }
        
        mock_build_data = {
            'number': 123,
            'building': False,
            'result': 'SUCCESS',
            'timestamp': 1640995200000,
            'actions': []
        }
        
        mock_config_data = """<?xml version="1.0" encoding="UTF-8"?>
        <project>
            <scm class="hudson.plugins.git.GitSCM">
                <userRemoteConfigs>
                    <hudson.plugins.git.UserRemoteConfig>
                        <url>https://github.com/test/repo.git</url>
                    </hudson.plugins.git.UserRemoteConfig>
                </userRemoteConfigs>
                <branches>
                    <hudson.plugins.git.BranchSpec>
                        <name>*/main</name>
                    </hudson.plugins.git.BranchSpec>
                </branches>
            </scm>
            <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition">
                <scriptPath>Jenkinsfile</scriptPath>
            </definition>
        </project>"""
        
        mock_batch.side_effect = [
            {
                'http://localhost:8080/job/test-job/api/json': (mock_job_data, None),
                'http://localhost:8080/job/test-job/config.xml': (mock_config_data, None)
            },
            {
                'http://test.com/job/test/123/api/json': (mock_build_data, None)
            }
        ]
        
        mock_recent_builds.return_value = [
            {'id': 123, 'status': 'SUCCESS'},
            {'id': 122, 'status': 'SUCCESS'}
        ]
        
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            job_info = manager.get_job_info('test-job')
            
            self.assertEqual(job_info.job_name, 'test-job')
            self.assertEqual(job_info.latest_build_id, 123)
            self.assertEqual(job_info.latest_build_status, 'SUCCESS')
            self.assertEqual(len(job_info.recent_builds), 2)
            
    @patch.object(JenkinsManager, '_get_jobs_from_folders')
    @patch.object(JenkinsManager, '_get_job_info_with_metadata')
    def test_get_all_jobs_summary_with_folders(self, mock_job_info, mock_folders):
        """Test getting all jobs summary with folder structure"""
        mock_folders.return_value = [
            JobInfo(job_name='test-job-1', folder_name='Test Folder'),
            JobInfo(job_name='test-job-2', folder_name='Test Folder')
        ]
        
        with patch('jenkins_manager.os.path.exists', return_value=True), \
             patch('builtins.open'), \
             patch('yaml.safe_load', return_value=self.test_config):
            
            manager = JenkinsManager()
            jobs = manager.get_all_jobs_summary()
            
            self.assertEqual(len(jobs), 2)
            self.assertEqual(jobs[0].folder_name, 'Test Folder')
            
    def test_parse_parameter_string(self):
        """Test parameter string parsing"""
        with patch('jenkins_manager.os.path.exists', return_value=False):
            manager = JenkinsManager()
            
            # Test simple parameters
            params = manager.parse_parameter_string("KEY1=value1, KEY2=value2")
            self.assertEqual(params['KEY1'], 'value1')
            self.assertEqual(params['KEY2'], 'value2')
            
            # Test complex parameters with JSON
            json_value = '{"service": "admin-ui", "version": "1.0"}'
            params = manager.parse_parameter_string(f"CONFIG={json_value}")
            self.assertEqual(params['CONFIG'], json_value)
            
    def test_job_info_dataclass(self):
        """Test JobInfo dataclass functionality"""
        job_info = JobInfo(
            job_name='test-job',
            latest_build_id=123,
            latest_build_status='SUCCESS'
        )
        
        self.assertEqual(job_info.job_name, 'test-job')
        self.assertEqual(job_info.latest_build_id, 123)
        self.assertEqual(job_info.latest_build_status, 'SUCCESS')
        self.assertEqual(job_info.recent_builds, [])  # Default empty list
        
        # Test conversion to dict
        job_dict = asdict(job_info)
        self.assertIn('job_name', job_dict)
        self.assertIn('recent_builds', job_dict)


class TestAppIntegration(unittest.TestCase):
    """Integration tests for Flask app"""
    
    def setUp(self):
        """Set up test app"""
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        
    @patch('app.jenkins_manager')
    def test_api_jobs_endpoint(self, mock_manager):
        """Test /api/jobs endpoint"""
        from app import app
        
        # Mock job data
        mock_job = JobInfo(
            job_name='test-job',
            latest_build_id=123,
            latest_build_status='SUCCESS',
            recent_builds=[
                {'id': 123, 'status': 'SUCCESS'},
                {'id': 122, 'status': 'FAILURE'}
            ]
        )
        
        mock_manager.get_all_jobs_summary.return_value = [mock_job]
        
        with app.test_client() as client:
            response = client.get('/api/jobs')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]['job_name'], 'test-job')
            self.assertEqual(len(data[0]['recent_builds']), 2)
            
    @patch('app.jenkins_manager')
    def test_api_environments_endpoint(self, mock_manager):
        """Test /api/environments endpoint"""
        from app import app
        
        mock_manager.get_environments.return_value = {
            'current': 'Test Environment',
            'legacy': 'Legacy Environment'
        }
        mock_manager.get_current_environment_info.return_value = {
            'key': 'current',
            'name': 'Test Environment',
            'url': 'http://test.com'
        }
        
        with app.test_client() as client:
            response = client.get('/api/environments')
            
            self.assertEqual(response.status_code, 200)
            data = json.loads(response.data)
            self.assertIn('environments', data)
            self.assertIn('current', data)


if __name__ == '__main__':
    # Set up test configuration
    unittest.main(verbosity=2) 