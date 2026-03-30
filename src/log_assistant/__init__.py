# Log Assistant Package

import os
import yaml
import logging

from .log_parser import LogParser, LogEntry
from .orchestrator import LogAssistantOrchestrator

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

__all__ = ['LogAssistantOrchestrator', 'LogParser', 'LogEntry', 'analyze', 'analyze_simple']


def load_config(config_path: str = "config/config.yaml"):
    """Load configuration from YAML file"""
    config_file = os.path.join(os.path.dirname(__file__), '..', '..', config_path)
    
    if not os.path.exists(config_file):
        logger.warning(f"Config file not found: {config_file}, using defaults")
        return get_default_config()
    
    with open(config_file, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # Replace environment variables
    config = _replace_env_vars(config)
    return config


def get_default_config():
    """Get default configuration"""
    return {
        "llm": {
            "provider": "minimax",
            "model": "MiniMax-M2.7",
            "api_key": os.environ.get('MINIMAX_API_KEY', ''),
            "temperature": 0.7,
            "max_tokens": 2000
        },
        "call_log": {
            "enabled": True,
            "log_file": "logs/calls.log"
        }
    }


def _replace_env_vars(config):
    """Replace ${VAR} with environment variables"""
    if isinstance(config, dict):
        return {k: _replace_env_vars(v) for k, v in config.items()}
    elif isinstance(config, list):
        return [_replace_env_vars(item) for item in config]
    elif isinstance(config, str) and config.startswith('${') and config.endswith('}'):
        var_name = config[2:-1]
        return os.environ.get(var_name, config)
    return config


def analyze(question: str, log_path: str,
           time_range=None, keywords=None, top_n=10, knowledge_text=None, config_path="config/config.yaml"):
    """
    Main analysis function
    
    Args:
        question: User's natural language question
        log_path: Path to log file
        time_range: Optional time range {"start": "ISO date", "end": "ISO date"}
        keywords: Optional keywords list
        top_n: Number of top items to return
        knowledge_text: Optional knowledge text (FAQ)
        config_path: Path to config file
        
    Returns:
        Dict with structured analysis output
    """
    # Load config
    config = load_config(config_path)
    
    # Validate inputs
    if not os.path.exists(log_path):
        return {
            "success": False,
            "error": f"Log file not found: {log_path}"
        }
    
    # Create orchestrator and process
    orchestrator = LogAssistantOrchestrator(config)
    result = orchestrator.process(
        user_question=question,
        log_path=log_path,
        time_range=time_range,
        keywords=keywords,
        top_n=top_n,
        knowledge_text=knowledge_text
    )
    
    return result


def analyze_simple(question: str, log_path: str, **kwargs):
    """
    Simple interface that returns markdown directly
    
    Args:
        question: User's natural language question
        log_path: Path to log file
        **kwargs: Additional arguments passed to analyze()
        
    Returns:
        Markdown formatted analysis report
    """
    result = analyze(question, log_path, **kwargs)
    
    if result.get('success'):
        return result.get('structured_output', {}).get('markdown', 'No output generated')
    else:
        return f"# 错误\n\n{result.get('error', 'Unknown error')}"
