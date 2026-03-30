"""
Unit Tests for Output Generator Module
"""

import pytest
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.log_assistant.output_generator import OutputGenerator


@pytest.fixture
def sample_llm_response():
    """Sample LLM response"""
    return {
        'success': True,
        'text': '''
## 1. 结论
系统运行正常，发现少量错误

## 2. 关键数据
- 总请求: 1000
- 5xx错误: 5

## 3. 建议
1. 检查数据库连接
2. 查看应用日志
'''
    }


@pytest.fixture
def sample_tool_results():
    """Sample tool results"""
    return [
        {
            'tool': 'analyze_log_stats',
            'success': True,
            'data': {
                'total_entries': 1000,
                'level_distribution': {'INFO': 900, 'WARNING': 95, 'ERROR': 5}
            }
        },
        {
            'tool': 'analyze_5xx_errors',
            'success': True,
            'data': {
                'total_5xx': 5,
                'status_distribution': {500: 3, 503: 2}
            }
        }
    ]


class TestOutputGenerator:
    """Test OutputGenerator class"""
    
    def test_generate_success(self, sample_llm_response, sample_tool_results):
        """Test successful output generation"""
        generator = OutputGenerator()
        
        result = generator.generate(
            user_question="分析日志错误",
            llm_response=sample_llm_response,
            tool_results=sample_tool_results,
            log_path="logs/test.log",
            time_range=None
        )
        
        assert 'question' in result
        assert result['question'] == "分析日志错误"
        assert 'markdown' in result
        assert 'analysis' in result
    
    def test_generate_markdown_format(self, sample_llm_response, sample_tool_results):
        """Test markdown output format"""
        generator = OutputGenerator()
        
        result = generator.generate(
            user_question="分析错误",
            llm_response=sample_llm_response,
            tool_results=sample_tool_results,
            log_path="logs/test.log"
        )
        
        markdown = result['markdown']
        
        # Should contain these sections
        assert '日志分析报告' in markdown
        assert '问题' in markdown
        assert '日志文件' in markdown
        assert '结论' in markdown
        assert '关键数据' in markdown
        assert '建议' in markdown
    
    def test_generate_with_time_range(self, sample_llm_response, sample_tool_results):
        """Test output with time range"""
        generator = OutputGenerator()
        
        time_range = {
            'start': '2026-03-30T10:00:00',
            'end': '2026-03-30T11:00:00'
        }
        
        result = generator.generate(
            user_question="分析错误",
            llm_response=sample_llm_response,
            tool_results=sample_tool_results,
            log_path="logs/test.log",
            time_range=time_range
        )
        
        assert result['time_range'] == time_range
        assert '时间范围' in result['markdown']
    
    def test_generate_llm_failure(self):
        """Test handling LLM failure"""
        generator = OutputGenerator()
        
        result = generator.generate(
            user_question="分析错误",
            llm_response={'success': False, 'error': 'API Error'},
            tool_results=[],
            log_path="logs/test.log"
        )
        
        assert 'error' in result
        assert 'markdown' in result
    
    def test_generate_error_output(self):
        """Test error output generation"""
        generator = OutputGenerator()
        
        result = generator.generate_error("Something went wrong")
        
        assert result['error'] is True
        assert 'Something went wrong' in result['message']
        assert 'markdown' in result
    
    def test_extract_key_data(self, sample_tool_results):
        """Test extracting key data from tool results"""
        generator = OutputGenerator()
        
        result = generator._extract_structured_data(sample_tool_results)
        
        assert 'log_stats' in result
        assert result['log_stats']['total_entries'] == 1000
        assert 'error_5xx' in result
        assert result['error_5xx']['total'] == 5
    
    def test_info_status_sufficient(self):
        """Test info status sufficient"""
        generator = OutputGenerator()
        
        status = generator._check_info_sufficient("分析结果如下，数据充分")
        assert status == "sufficient"
    
    def test_info_status_insufficient(self):
        """Test info status insufficient"""
        generator = OutputGenerator()
        
        status = generator._check_info_sufficient("信息不足，需要更多数据")
        assert status == "insufficient"