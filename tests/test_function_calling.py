"""
Unit Tests for Function Calling Module
Tests for analyze_404_errors and analyze_response_time
"""

import pytest
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.log_assistant.function_calling import (
    execute_tool, TOOL_DEFINITIONS
)


@pytest.fixture
def iis_log_file(tmp_path):
    """Create IIS format log file for testing"""
    log_content = """#Software: Microsoft Internet Information Services 7.5
#Version: 1.0
#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip cs(User-Agent) sc-status sc-substatus sc-win32-status time-taken
2017-07-04 00:00:00 172.30.210.81 GET /api/users - 443 - 27.190.154.65 Mozilla 200 0 0 100
2017-07-04 00:00:01 172.30.210.81 GET /api/login - 443 - 124.126.91.147 Mozilla 401 0 64 129807
2017-07-04 00:00:02 172.30.210.81 GET /missing1 - 443 - 27.190.154.65 Mozilla 404 0 0 50
2017-07-04 00:00:03 172.30.210.81 GET /missing2 - 443 - 27.190.154.65 Mozilla 404 0 0 50
2017-07-04 00:00:04 172.30.210.81 GET /api/error - 443 - 58.246.59.145 Mozilla 500 0 0 5000
2017-07-04 00:00:05 172.30.210.81 GET /api/slow1 - 443 - 58.246.59.145 Mozilla 200 0 0 30000
2017-07-04 00:00:06 172.30.210.81 GET /api/slow2 - 443 - 58.246.59.145 Mozilla 200 0 0 25000
2017-07-04 00:00:07 172.30.210.81 GET /missing3 - 443 - 124.126.91.147 Mozilla 404 0 0 50
"""
    log_file = tmp_path / "test.log"
    log_file.write_text(log_content)
    return str(log_file)


class TestToolDefinitions:
    """Test tool definitions"""
    
    def test_tool_definitions_exist(self):
        """Verify all tool definitions exist"""
        tool_names = [t['name'] for t in TOOL_DEFINITIONS]
        
        assert 'analyze_log_stats' in tool_names
        assert 'analyze_5xx_errors' in tool_names
        assert 'search_error_patterns' in tool_names
        assert 'search_keywords' in tool_names
        assert 'analyze_404_errors' in tool_names
        assert 'analyze_response_time' in tool_names
    
    def test_tool_definitions_have_schema(self):
        """Verify each tool has input schema"""
        for tool in TOOL_DEFINITIONS:
            assert 'input_schema' in tool
            assert 'properties' in tool['input_schema']


class TestAnalyze404Errors:
    """Test analyze_404_errors function"""
    
    def test_analyze_404_errors_success(self, iis_log_file):
        """Test 404 error analysis"""
        result = execute_tool('analyze_404_errors', {'log_path': iis_log_file, 'top_n': 10})
        
        assert result['success'] is True
        # Data is nested
        data = result['data']['data'] if 'data' in result else result
        assert data['total_404'] == 3
    
    def test_analyze_404_errors_top_paths(self, iis_log_file):
        """Test 404 error top paths"""
        result = execute_tool('analyze_404_errors', {'log_path': iis_log_file, 'top_n': 5})
        
        assert result['success'] is True
        data = result['data']['data'] if 'data' in result else result
        top_paths = data['top_paths']
        assert len(top_paths) >= 1
    
    def test_analyze_404_errors_top_ips(self, iis_log_file):
        """Test 404 error top IPs"""
        result = execute_tool('analyze_404_errors', {'log_path': iis_log_file, 'top_n': 5})
        
        assert result['success'] is True
        data = result['data']['data'] if 'data' in result else result
        top_ips = data['top_ips']
        assert '27.190.154.65' in top_ips


class TestAnalyzeResponseTime:
    """Test analyze_response_time function"""
    
    def test_analyze_response_time_success(self, iis_log_file):
        """Test response time analysis"""
        result = execute_tool('analyze_response_time', {'log_path': iis_log_file, 'top_n': 5})
        
        assert result['success'] is True
        data = result['data']['data'] if 'data' in result else result
        assert data['total_slow_requests'] >= 2
    
    def test_analyze_response_time_order(self, iis_log_file):
        """Test slowest requests are first"""
        result = execute_tool('analyze_response_time', {'log_path': iis_log_file, 'top_n': 5})
        
        assert result['success'] is True
        data = result['data']['data'] if 'data' in result else result
        slowest = data['slowest_requests']
        
        # Should be sorted by time_taken_ms descending
        if len(slowest) >= 2:
            assert slowest[0]['time_taken_ms'] >= slowest[1]['time_taken_ms']
    
    def test_analyze_response_time_metadata(self, iis_log_file):
        """Test response time includes required metadata"""
        result = execute_tool('analyze_response_time', {'log_path': iis_log_file, 'top_n': 5})
        
        assert result['success'] is True
        data = result['data']['data'] if 'data' in result else result
        slowest = data['slowest_requests']
        
        if slowest:
            assert 'time_taken_ms' in slowest[0]
            assert 'message' in slowest[0]


class TestExecuteTool:
    """Test execute_tool function"""
    
    def test_execute_tool_unknown(self):
        """Test unknown tool returns error"""
        result = execute_tool('unknown_tool', {'log_path': '/test.log'})
        
        assert result['success'] is False
        assert 'Unknown tool' in result['error']
    
    def test_execute_tool_analyze_log_stats(self, iis_log_file):
        """Test execute_tool with analyze_log_stats"""
        result = execute_tool('analyze_log_stats', {'log_path': iis_log_file, 'top_n': 10})
        
        assert result['success'] is True
        assert 'total_entries' in result['data']
    
    def test_execute_tool_with_time_range(self, iis_log_file):
        """Test tool execution with time range"""
        time_range = {
            'start': '2017-07-04T00:00:00',
            'end': '2017-07-04T00:00:04'
        }
        result = execute_tool('analyze_log_stats', {
            'log_path': iis_log_file,
            'time_range': time_range,
            'top_n': 10
        })
        
        assert result['success'] is True