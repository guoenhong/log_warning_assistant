"""
Unit Tests for Log Parser Module
"""

import pytest
import os
from datetime import datetime

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
