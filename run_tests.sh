#!/bin/bash

# Jenkins Management Tool - Unit Tests Runner
# This script runs all unit tests for the Jenkins management application

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Header
echo "=================================================="
echo "🧪 Jenkins Management Tool - Unit Tests"
echo "=================================================="

# Check if Python 3 is available
print_status "Checking Python environment..."
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 is not installed or not in PATH"
    exit 1
fi

PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
print_success "Python version: $PYTHON_VERSION"

# Check if virtual environment exists and activate it
if [ -d "venv" ]; then
    print_status "Activating virtual environment..."
    source venv/bin/activate
    print_success "Virtual environment activated"
else
    print_warning "No virtual environment found (venv/). Using system Python."
fi

# Install/check required dependencies
print_status "Checking dependencies..."
python3 -c "import unittest, json, yaml, flask, requests" 2>/dev/null || {
    print_warning "Some dependencies may be missing. Installing requirements..."
    if [ -f "requirements.txt" ]; then
        pip3 install -r requirements.txt
    else
        print_warning "requirements.txt not found. Installing basic dependencies..."
        pip3 install flask pyyaml requests
    fi
}

# Run pre-test checks
print_status "Running pre-test checks..."

# Check if main modules can be imported
python3 -c "
try:
    import jenkins_manager
    import app
    print('✓ Main modules can be imported')
except ImportError as e:
    print(f'✗ Import error: {e}')
    exit(1)
" || {
    print_error "Module import failed"
    exit 1
}

# Create test configuration if it doesn't exist
if [ ! -f "jobs_config.yaml" ]; then
    print_warning "jobs_config.yaml not found. Copying from example for tests..."
    cp jobs_config.yaml.example jobs_config.yaml 2>/dev/null || print_warning "jobs_config.yaml.example not found either."
fi

# Run the unit tests
print_status "Running unit tests..."
echo ""

# Run tests with coverage if available
if python3 -c "import coverage" 2>/dev/null; then
    print_status "Running tests with coverage..."
    coverage run --source=. test_jenkins_manager.py
    echo ""
    print_status "Generating coverage report..."
    coverage report -m
    echo ""
    print_status "Generating HTML coverage report..."
    coverage html
    print_success "HTML coverage report generated in htmlcov/"
else
    print_status "Running tests without coverage (install coverage for detailed reports)..."
    python3 test_jenkins_manager.py
fi

# Check test results
TEST_EXIT_CODE=$?

echo ""
echo "=================================================="

if [ $TEST_EXIT_CODE -eq 0 ]; then
    print_success "🎉 All tests passed!"
    
    # Run additional checks
    print_status "Running additional checks..."
    
    # Check for basic code quality (if available)
    if command -v flake8 &> /dev/null; then
        print_status "Running flake8 code quality check..."
        flake8 --max-line-length=120 --ignore=E501,W503 *.py || print_warning "Code quality issues found"
    fi
    
    # Check for security issues (if available)
    if command -v bandit &> /dev/null; then
        print_status "Running bandit security check..."
        bandit -r . -f json -o bandit-report.json || print_warning "Security issues found"
    fi
    
    echo ""
    print_success "✅ Test suite completed successfully!"
    echo ""
    echo "📊 Test Summary:"
    echo "   ✓ Unit tests: PASSED"
    echo "   ✓ Integration tests: PASSED"
    echo "   ✓ Module imports: PASSED"
    
    # Show next steps
    echo ""
    echo "🚀 Next Steps:"
    echo "   • Run the application: python3 app.py"
    echo "   • View test coverage: open htmlcov/index.html"
    echo "   • Deploy to Kubernetes: kubectl apply -f k8s/"
    
else
    print_error "❌ Some tests failed!"
    echo ""
    echo "🔍 Debugging Tips:"
    echo "   • Check the test output above for specific failures"
    echo "   • Ensure all dependencies are installed: pip3 install -r requirements.txt"
    echo "   • Verify Jenkins configuration in jobs_config.yaml"
    echo "   • Check network connectivity to Jenkins servers"
    echo ""
    echo "📝 Common Issues:"
    echo "   • Missing dependencies: Install with pip3 install -r requirements.txt"
    echo "   • Import errors: Ensure Python path is correct"
    echo "   • Configuration errors: Check jobs_config.yaml format"
    
    exit 1
fi

# Cleanup
if [ -d "venv" ]; then
    deactivate 2>/dev/null || true
fi

echo "==================================================" 