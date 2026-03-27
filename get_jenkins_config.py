#!/usr/bin/env python3

import os
import requests
import json
import re
from urllib.parse import urlparse, unquote
import xml.etree.ElementTree as ET

# Jenkins credentials — set via environment variables or edit directly for local use
JENKINS_URL = os.environ.get("JENKINS_URL", "http://localhost:8080")
JENKINS_USER = os.environ.get("JENKINS_USER", "admin")
JENKINS_TOKEN = os.environ.get("JENKINS_TOKEN", "")

def get_job_name_from_url(job_url):
    """Extract job name from Jenkins job URL"""
    # Remove trailing slash and get the last part
    path = urlparse(job_url).path.rstrip('/')
    # Split by '/' and find the part after 'job'
    parts = path.split('/')
    try:
        job_index = parts.index('job')
        if job_index + 1 < len(parts):
            return unquote(parts[job_index + 1])
    except ValueError:
        pass
    return None

def get_job_config(job_name):
    """Get job configuration XML from Jenkins API"""
    config_url = f"{JENKINS_URL}/job/{job_name}/config.xml"
    
    try:
        response = requests.get(
            config_url,
            auth=(JENKINS_USER, JENKINS_TOKEN),
            timeout=30
        )
        
        if response.status_code == 200:
            return response.text
        else:
            print(f"Failed to get config for {job_name}: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Error getting config for {job_name}: {e}")
        return None

def extract_jenkinsfile_path(config_xml):
    """Extract Jenkinsfile path from job configuration XML"""
    try:
        root = ET.fromstring(config_xml)
        
        # For Pipeline jobs, look for scriptPath
        script_path_elem = root.find('.//scriptPath')
        if script_path_elem is not None and script_path_elem.text:
            return script_path_elem.text
        
        # For Multibranch Pipeline, look for scriptPath in source
        for script_elem in root.findall('.//scriptPath'):
            if script_elem.text:
                return script_elem.text
        
        # Look for script content directly (inline pipeline)
        script_elem = root.find('.//script')
        if script_elem is not None and script_elem.text:
            return "Inline Pipeline Script"
        
        # Check for SCM configuration
        scm_elem = root.find('.//scm')
        if scm_elem is not None:
            scm_class = scm_elem.get('class', '')
            if 'GitSCM' in scm_class or 'SubversionSCM' in scm_class:
                return "Jenkinsfile (default)"
        
        return "Not found"
        
    except ET.ParseError as e:
        print(f"Failed to parse XML: {e}")
        return "Parse error"

def get_job_info(job_name):
    """Get basic job information from Jenkins API"""
    job_url = f"{JENKINS_URL}/job/{job_name}/api/json"
    
    try:
        response = requests.get(
            job_url,
            auth=(JENKINS_USER, JENKINS_TOKEN),
            timeout=30
        )
        
        if response.status_code == 200:
            job_data = response.json()
            return {
                'name': job_data.get('name', job_name),
                'description': job_data.get('description', ''),
                'class': job_data.get('_class', ''),
                'buildable': job_data.get('buildable', False)
            }
        else:
            return None
            
    except Exception as e:
        print(f"Error getting job info for {job_name}: {e}")
        return None

def main():
    # Read job URLs from job.md
    job_urls = []
    try:
        with open('job.md', 'r') as f:
            for line in f:
                line = line.strip()
                if line and line.startswith('http'):
                    # Remove any comments after #
                    job_url = line.split('#')[0].strip()
                    job_urls.append(job_url)
    except FileNotFoundError:
        print("job.md file not found!")
        return

    results = []
    
    for job_url in job_urls:
        print(f"Processing: {job_url}")
        
        job_name = get_job_name_from_url(job_url)
        if not job_name:
            print(f"Could not extract job name from URL: {job_url}")
            results.append({
                'job_url': job_url,
                'job_name': 'Unknown',
                'jenkinsfile_path': 'URL parse error',
                'job_type': 'Unknown',
                'description': ''
            })
            continue
        
        # Get job basic info
        job_info = get_job_info(job_name)
        
        # Get job configuration
        config_xml = get_job_config(job_name)
        if config_xml:
            jenkinsfile_path = extract_jenkinsfile_path(config_xml)
        else:
            jenkinsfile_path = "Config not accessible"
        
        job_type = "Unknown"
        description = ""
        
        if job_info:
            job_type = job_info['class'].split('.')[-1] if job_info['class'] else "Unknown"
            description = job_info.get('description', '')
        
        results.append({
            'job_url': job_url,
            'job_name': job_name,
            'jenkinsfile_path': jenkinsfile_path,
            'job_type': job_type,
            'description': description
        })
    
    # Generate markdown table
    markdown_content = f"""# Jenkins Jobs Configuration Report

Generated on: {requests.get(f'{JENKINS_URL}/api/json').headers.get('Date', 'Unknown')}

## Summary

Total jobs analyzed: {len(results)}

## Jobs Configuration Table

| Job Name | Job Type | Jenkinsfile Path | Description | Job URL |
|----------|----------|------------------|-------------|---------|
"""
    
    for result in results:
        # Escape pipe characters in content
        job_name = result['job_name'].replace('|', '\\|')
        job_type = result['job_type'].replace('|', '\\|')
        jenkinsfile_path = result['jenkinsfile_path'].replace('|', '\\|')
        description = (result['description'] or '').replace('|', '\\|').replace('\n', ' ')[:100]
        job_url = result['job_url']
        
        markdown_content += f"| {job_name} | {job_type} | {jenkinsfile_path} | {description} | {job_url} |\n"
    
    # Write to markdown file
    with open('jenkins_jobs_config.md', 'w') as f:
        f.write(markdown_content)
    
    print(f"\nReport generated: jenkins_jobs_config.md")
    print(f"Total jobs processed: {len(results)}")

if __name__ == "__main__":
    main() 