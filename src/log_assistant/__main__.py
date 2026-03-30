"""
CLI entry point for Log Warning Assistant

Usage:
    python -m src.log_assistant "问题" 日志文件路径
    python -m src.log_assistant "分析错误" logs/access.log --top-n 20
"""

import sys
import argparse
import logging

# Setup UTF-8 output for Windows
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from . import analyze

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(description='Log Warning Assistant')
    parser.add_argument('question', help='Natural language question about logs')
    parser.add_argument('log_path', help='Path to log file')
    parser.add_argument('--time-start', help='Start time (ISO format)')
    parser.add_argument('--time-end', help='End time (ISO format)')
    parser.add_argument('--keywords', help='Comma-separated keywords')
    parser.add_argument('--top-n', type=int, default=10, help='Top N items')
    parser.add_argument('--knowledge', help='Knowledge text file')
    parser.add_argument('--output', help='Output file path')
    
    args = parser.parse_args()
    
    # Build time_range
    time_range = None
    if args.time_start or args.time_end:
        time_range = {}
        if args.time_start:
            time_range['start'] = args.time_start
        if args.time_end:
            time_range['end'] = args.time_end
    
    # Parse keywords
    keywords = None
    if args.keywords:
        keywords = [k.strip() for k in args.keywords.split(',')]
    
    # Load knowledge text
    knowledge_text = None
    if args.knowledge:
        try:
            with open(args.knowledge, 'r', encoding='utf-8') as f:
                knowledge_text = f.read()
        except FileNotFoundError:
            logger.warning(f"Knowledge file not found: {args.knowledge}")
    
    # Run analysis
    try:
        result = analyze(
            question=args.question,
            log_path=args.log_path,
            time_range=time_range,
            keywords=keywords,
            top_n=args.top_n,
            knowledge_text=knowledge_text
        )
        
        if result.get('success'):
            output = result.get('structured_output', {}).get('markdown', 
                              result.get('error', 'No output generated'))
            print(output)
            
            # Show auto-saved report path
            report_path = result.get('report_path')
            if report_path:
                print(f"\n📄 报告已自动保存至: {report_path}")
            
            # Save to file if specified
            if args.output:
                with open(args.output, 'w', encoding='utf-8') as f:
                    f.write(output)
                print(f"\n[Output saved to {args.output}]")
        else:
            print(f"Error: {result.get('error', 'Unknown error')}")
            sys.exit(1)
            
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
