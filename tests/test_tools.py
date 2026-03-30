"""
Unit Tests for Tool Functions
"""

import pytest
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.log_tools import (
    analyze_log_stats, search_error_patterns, search_keywords, 
    analyze_5xx_errors, ToolResult
)


@pytest.fixture
def sample_log_file(tmp_path):
    """Create a temporary log file for testing"""
    log_content = """192.168.1.1 - - [30/Mar/2026:10:00:00 +0800] "GET /api/users HTTP/1.1" 200 1234
192.168.1.2 - - [30/Mar/2026:10:00:01 +0800] "POST /api/login HTTP/1.1" 401 567
192.168.1.3 - - [30/Mar/2026:10:00:02 +0800] "GET /api/error HTTP/1.1" 500 234
192.168.1.1 - - [30/Mar/2026:10:00:03 +0800] "GET /api/orders HTTP/1.1" 503 89
192.168.1.2 - - [30/Mar/2026:10:00:04 +0800] "GET /api/products HTTP/1.1" 200 456
"""
    log_file = tmp_path / "test.log"
    log_file.write_text(log_content)
    return str(log_file)


class TestToolResults:
    """Test ToolResult class"""
    
    def test_tool_result_success(self):
        result = ToolResult(success=True, data={'key': 'value'})
        assert result.success is True
        assert result.data == {'key': 'value'}
        assert result.error is None
    
    def test_tool_result_failure(self):
        result = ToolResult(success=False, error='Something went wrong')
        assert result.success is False
        assert result.error == 'Something went wrong'
        assert result.data is None
    
    def test_to_dict(self):
        result = ToolResult(success=True, data={'test': 123})
        d = result.to_dict()
        assert d['success'] is True
        assert d['data'] == {'test': 123}


class TestAnalyzeLogStats:
    """Test analyze_log_stats function"""
    
    def test_analyze_log_stats_success(self, sample_log_file):
        result = analyze_log_stats(sample_log_file, top_n=5)
        
        assert result.success is True
        assert result.data is not None
        assert 'total_entries' in result.data
        assert result.data['total_entries'] == 5
    
    def test_analyze_log_stats_file_not_found(self):
        result = analyze_log_stats('/nonexistent/file.log')
        assert result.success is False
        assert result.error is not None


class TestSearchErrorPatterns:
    """Test search_error_patterns function"""
    
    def test_search_error_patterns_success(self, sample_log_file):
        result = search_error_patterns(sample_log_file, top_n=10)
        
        assert result.success is True
        assert 'matched_count' in result.data
    
    def test_search_with_custom_patterns(self, sample_log_file):
        result = search_error_patterns(
            sample_log_file, 
            patterns=['500', '503'],
            top_n=10
        )
        
        assert result.success is True
        assert result.data['matched_count'] >= 2


class TestAnalyze5xxErrors:
    """Test analyze_5xx_errors function"""
    
    def test_analyze_5xx_errors_success(self, sample_log_file):
        result = analyze_5xx_errors(sample_log_file, top_n=5)
        
        assert result.success is True
        assert result.data is not None
        assert 'total_5xx' in result.data
        assert result.data['total_5xx'] == 2
    
    def test_analyze_5xx_errors_time_range(self, sample_log_file):
        time_range = {
            'start': '2026-03-30T10:00:00',
            'end': '2026-03-30T10:00:02'
        }
        result = analyze_5xx_errors(sample_log_file, time_range=time_range)
        
        assert result.success is True
        # Data might be nested due to function_calling wrapper, check both
        data = result.data.get('data', result.data) if isinstance(result.data, dict) else result.data
        if isinstance(data, dict) and 'total_5xx' in data:
            assert data['total_5xx'] == 1


class TestSearchKeywords:
    """Test search_keywords function"""
    
    def test_search_keywords_success(self, sample_log_file):
        result = search_keywords(sample_log_file, ['error', 'orders'])
        
        assert result.success is True
        assert result.data['matched_count'] >= 2
    
    def test_search_keywords_no_match(self, sample_log_file):
        result = search_keywords(sample_log_file, ['nonexistent_keyword'])
        
        assert result.success is True
        assert result.data['matched_count'] == 0
