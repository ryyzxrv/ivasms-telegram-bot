"""
Unit tests for the storage manager.
"""

import asyncio
import os
import tempfile
import pytest
from datetime import datetime, timedelta

import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from src.storage import StorageManager


@pytest.fixture
async def storage_manager():
    """Create a temporary storage manager for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as tmp_file:
        db_path = tmp_file.name
    
    storage = StorageManager(db_path)
    await storage.initialize()
    
    yield storage
    
    await storage.close()
    
    # Clean up
    if os.path.exists(db_path):
        os.unlink(db_path)


@pytest.fixture
def sample_otp():
    """Sample OTP data for testing."""
    return {
        'id': 'test_otp_123',
        'timestamp': '2025-09-30 12:00:00',
        'from_number': '+1234567890',
        'text': 'Your verification code is 123456',
        'service': 'TestService'
    }


@pytest.mark.asyncio
async def test_store_and_retrieve_otp(storage_manager, sample_otp):
    """Test storing and retrieving OTPs."""
    # Store OTP
    success = await storage_manager.store_otp(sample_otp)
    assert success is True
    
    # Check if OTP exists
    exists = await storage_manager.otp_exists(sample_otp['id'])
    assert exists is True
    
    # Get recent OTPs
    recent_otps = await storage_manager.get_recent_otps(1)
    assert len(recent_otps) == 1
    assert recent_otps[0]['id'] == sample_otp['id']
    assert recent_otps[0]['text'] == sample_otp['text']


@pytest.mark.asyncio
async def test_get_last_otp(storage_manager, sample_otp):
    """Test getting the last OTP."""
    # Initially no OTPs
    last_otp = await storage_manager.get_last_otp()
    assert last_otp is None
    
    # Store OTP
    await storage_manager.store_otp(sample_otp)
    
    # Get last OTP
    last_otp = await storage_manager.get_last_otp()
    assert last_otp is not None
    assert last_otp['id'] == sample_otp['id']


@pytest.mark.asyncio
async def test_otp_count(storage_manager, sample_otp):
    """Test OTP counting."""
    # Initially zero
    count = await storage_manager.get_otp_count()
    assert count == 0
    
    # Store OTP
    await storage_manager.store_otp(sample_otp)
    
    # Count should be 1
    count = await storage_manager.get_otp_count()
    assert count == 1
    
    # Store another OTP
    sample_otp2 = sample_otp.copy()
    sample_otp2['id'] = 'test_otp_456'
    await storage_manager.store_otp(sample_otp2)
    
    # Count should be 2
    count = await storage_manager.get_otp_count()
    assert count == 2


@pytest.mark.asyncio
async def test_state_management(storage_manager):
    """Test bot state management."""
    # Initially no state
    value = await storage_manager.get_state('test_key')
    assert value is None
    
    # Set state
    await storage_manager.set_state('test_key', 'test_value')
    
    # Get state
    value = await storage_manager.get_state('test_key')
    assert value == 'test_value'
    
    # Get with default
    value = await storage_manager.get_state('nonexistent_key', 'default')
    assert value == 'default'


@pytest.mark.asyncio
async def test_last_seen_otp_id(storage_manager):
    """Test last seen OTP ID management."""
    # Initially None
    last_id = await storage_manager.get_last_seen_otp_id()
    assert last_id is None
    
    # Set last seen ID
    await storage_manager.set_last_seen_otp_id('test_id_123')
    
    # Get last seen ID
    last_id = await storage_manager.get_last_seen_otp_id()
    assert last_id == 'test_id_123'


@pytest.mark.asyncio
async def test_get_all_states(storage_manager):
    """Test getting all states."""
    # Initially empty
    states = await storage_manager.get_all_states()
    assert len(states) == 0
    
    # Set multiple states
    await storage_manager.set_state('key1', 'value1')
    await storage_manager.set_state('key2', 'value2')
    
    # Get all states
    states = await storage_manager.get_all_states()
    assert len(states) == 2
    assert states['key1'] == 'value1'
    assert states['key2'] == 'value2'


@pytest.mark.asyncio
async def test_clear_state(storage_manager):
    """Test clearing states."""
    # Set state
    await storage_manager.set_state('test_key', 'test_value')
    
    # Verify it exists
    value = await storage_manager.get_state('test_key')
    assert value == 'test_value'
    
    # Clear state
    cleared = await storage_manager.clear_state('test_key')
    assert cleared is True
    
    # Verify it's gone
    value = await storage_manager.get_state('test_key')
    assert value is None
    
    # Clear non-existent state
    cleared = await storage_manager.clear_state('nonexistent_key')
    assert cleared is False


@pytest.mark.asyncio
async def test_database_info(storage_manager, sample_otp):
    """Test database info retrieval."""
    # Get initial info
    info = await storage_manager.get_database_info()
    assert 'db_path' in info
    assert 'otp_count' in info
    assert info['otp_count'] == 0
    
    # Store OTP
    await storage_manager.store_otp(sample_otp)
    
    # Get updated info
    info = await storage_manager.get_database_info()
    assert info['otp_count'] == 1
    assert info['db_size_bytes'] > 0


@pytest.mark.asyncio
async def test_duplicate_otp_handling(storage_manager, sample_otp):
    """Test handling of duplicate OTPs."""
    # Store OTP twice
    success1 = await storage_manager.store_otp(sample_otp)
    success2 = await storage_manager.store_otp(sample_otp)
    
    assert success1 is True
    assert success2 is True  # Should succeed (replace)
    
    # Should still have only one OTP
    count = await storage_manager.get_otp_count()
    assert count == 1


@pytest.mark.asyncio
async def test_recent_otps_limit(storage_manager):
    """Test recent OTPs with limit."""
    # Store multiple OTPs
    for i in range(5):
        otp = {
            'id': f'test_otp_{i}',
            'timestamp': f'2025-09-30 12:0{i}:00',
            'from_number': '+1234567890',
            'text': f'Code {i}',
            'service': 'TestService'
        }
        await storage_manager.store_otp(otp)
    
    # Get recent OTPs with limit
    recent_otps = await storage_manager.get_recent_otps(3)
    assert len(recent_otps) == 3
    
    # Should be in reverse chronological order (most recent first)
    assert recent_otps[0]['id'] == 'test_otp_4'
    assert recent_otps[1]['id'] == 'test_otp_3'
    assert recent_otps[2]['id'] == 'test_otp_2'


if __name__ == "__main__":
    pytest.main([__file__])
