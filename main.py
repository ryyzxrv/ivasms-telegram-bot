#!/usr/bin/env python3
"""
Main entry point for the iVASMS Telegram Bot.
"""

import asyncio
import sys
import os

# Add src directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.bot import main

if __name__ == "__main__":
    asyncio.run(main())
