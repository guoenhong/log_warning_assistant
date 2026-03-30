"""
Unit Tests for Log Parser Module
"""

import pytest
import os
import sys
from datetime import datetime

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.log_assistant.log_parser import LogParser, LogEntry


@pytest.fixture
def sample_log_file(tmp_path):
    """Create a temporary log file for testing"""
    log_content = """192.168.1.1 - - [30/Mar/2026:10:00:00 +0800] "GET /api/users HTTP/1.1" 200 1234
192.168.1.2 - - [30/Mar/2026:10:00:01 +0800] "POST /api/login HTTP/1.1" 401 567
192.168.1.3 - - [30/Mar/2026:10:00:02 +0800] "GET /api/error HTTP/1.1" 500 234
"""
    log_file = tmp_path / "test.log"
    log_file.write_text(log_content)
    return str(log_file)


@pytest.fixture
def simple_log_file(tmp_path):
    """Create a simple timestamp log file"""
    log_content = """2026-03-30 10:00:00 INFO Application started
2026-03-30 10:00:01 WARNING High memory usage
2026-03-30 10:00:02 ERROR Database connection failed
2026-03-30 10:00:03 ERROR Timeout error
"""
    log_file = tmp_path / "app.log"
    log_file.write_text(log_content)
    return str(log_file)


@pytest.fixture
def iis_log_file(tmp_path):
    """Create IIS W3C format log file"""
    log_content = """#Software: Microsoft Internet Information Services 7.5
#Version: 1.0
#Date: 2017-07-04 00:00:00
#Fields: date time s-ip cs-method cs-uri-stem cs-uri-query s-port cs-username c-ip cs(User-Agent) sc-status sc-substatus sc-win32-status time-taken
2017-07-04 00:00:00 172.30.210.81 GET /api/users - 443 - 27.190.154.65 Mozilla/4.0 200 0 0 312
2017-07-04 00:00:01 172.30.210.81 POST /api/login - 443 - 124.126.91.147 Mozilla/5.0 401 0 64 129807
2017-07-04 00:00:02 172.30.210.81 GET /api/error - 443 - 58.246.59.145 Mozilla/5.0 500 0 0 5000
2017-07-04 00:00:03 172.30.210.81 GET /notfound - 443 - 27.190.154.65 Mozilla/4.0 404 0 0 100
2017-07-04 00:00:04 172.30.210.81 GET /api/slow - 443 - 58.246.59.145 Mozilla/5.0 200 0 0 30000
"""
    log_file = tmp_path / "iis.log"
    log_file.write_text(log_content)
    return str(log_file)


@pytest.fixture
def json_log_file(tmp_path):
    """Create JSON format log file"""
    log_content = """{"timestamp": "2026-03-30T10:00:00", "level": "INFO", "message": "Server started"}
{"timestamp": "2026-03-30T10:00:01", "level": "ERROR", "message": "Database connection failed"}
{"timestamp": "2026-03-30T10:00:02", "level": "WARNING", "message": "High memory usage: 85%"}
"""
    log_file = tmp_path / "app.json"
    log_file.write_text(log_content)
    return str(log_file)


class TestLogParser:
    """Test cases for LogParser"""
    
    def test_parse_combined_log(self, sample_log_file):
        """Test parsing Nginx/Apache combined log format"""
        parser = LogParser()
        entries = parser.parse_file(sample_log_file)
        
        assert len(entries) == 3
        assert entries[0].metadata.get('ip') == '192.168.1.1'
        assert entries[0].metadata.get('status') == 200
        assert entries[2].metadata.get('status') == 500
    
    def test_parse_simple_log(self, simple_log_file):
        """Test parsing simple timestamp + level + message format"""
        parser = LogParser()
        entries = parser.parse_file(simple_log_file)
        
        assert len(entries) == 4
        assert entries[0].level == 'INFO'
        assert entries[2].level == 'ERROR'
        assert 'Database connection failed' in entries[2].message
    
    def test_filter_by_level(self, simple_log_file):
        """Test filtering entries by log level"""
        parser = LogParser()
        entries = parser.parse_file(simple_log_file)
        
        errors = parser.filter_by_level(['ERROR'])
        assert len(errors) == 2
        assert all(e.level == 'ERROR' for e in errors)
    
    def test_filter_by_keyword(self, simple_log_file):
        """Test filtering entries by keyword"""
        parser = LogParser()
        entries = parser.parse_file(simple_log_file)
        
        db_entries = parser.filter_by_keyword('database')
        assert len(db_entries) == 1
        assert 'Database' in db_entries[0].message
    
    def test_http_status_to_level(self):
        """Test HTTP status code to log level conversion"""
        parser = LogParser()
        
        assert parser._http_status_to_level(200) == 'INFO'
        assert parser._http_status_to_level(404) == 'WARNING'
        assert parser._http_status_to_level(500) == 'ERROR'
        assert parser._http_status_to_level(503) == 'ERROR'
    
    def test_parse_iis_log(self, iis_log_file):
        """Test parsing IIS W3C Extended Log Format"""
        parser = LogParser()
        entries = parser.parse_file(iis_log_file)
        
        # Should skip header lines (4 lines) and parse 5 log entries
        assert len(entries) == 5
        
        # First entry
        assert entries[0].metadata.get('ip') == '27.190.154.65'
        assert entries[0].metadata.get('status') == 200
        assert entries[0].level == 'INFO'
        
        # 500 error
        assert entries[2].metadata.get('status') == 500
        assert entries[2].level == 'ERROR'
        
        # 404 error
        assert entries[3].metadata.get('status') == 404
        assert entries[3].level == 'WARNING'
    
    def test_parse_json_log(self, json_log_file):
        """Test parsing JSON format logs"""
        parser = LogParser()
        entries = parser.parse_file(json_log_file)
        
        assert len(entries) == 3
        assert entries[0].level == 'INFO'
        assert entries[1].level == 'ERROR'
        assert entries[2].level == 'WARNING'
        assert 'Database connection failed' in entries[1].message
    
    def test_filter_by_time_range(self, iis_log_file):
        """Test filtering entries by time range"""
        parser = LogParser()
        entries = parser.parse_file(iis_log_file)
        
        from datetime import datetime
        start = datetime(2017, 7, 4, 0, 0, 2)
        end = datetime(2017, 7, 4, 0, 0, 4)
        
        filtered = parser.filter_by_time_range(start, end)
        assert len(filtered) == 3  # entries at 00:00:02, 00:00:03, 00:00:04
    
    def test_detect_level(self):
        """Test log level detection from message content"""
        parser = LogParser()
        
        assert parser._detect_level('ERROR: connection failed') == 'ERROR'
        assert parser._detect_level('WARN: memory high') == 'WARNING'
        assert parser._detect_level('DEBUG: variable x') == 'DEBUG'
        assert parser._detect_level('Normal log message') == 'INFO'


class TestLogEntry:
    """Test cases for LogEntry"""
    
    def test_log_entry_creation(self):
        """Test LogEntry object creation"""
        entry = LogEntry(
            timestamp=datetime.now(),
            level='ERROR',
            message='Test error message',
            raw='raw log line',
            metadata={'ip': '127.0.0.1'}
        )
        
        assert entry.level == 'ERROR'
        assert entry.message == 'Test error message'
        assert entry.metadata['ip'] == '127.0.0.1'
    
    def test_to_dict(self):
        """Test LogEntry to_dict conversion"""
        entry = LogEntry(
            timestamp=datetime(2026, 3, 30, 10, 0, 0),
            level='INFO',
            message='Test',
            raw='raw',
            metadata={}
        )
        
        d = entry.to_dict()
        assert d['timestamp'] == '2026-03-30T10:00:00'
        assert d['level'] == 'INFO'
        assert d['message'] == 'Test'
