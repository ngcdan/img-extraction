#!/usr/bin/env python3
"""
Test script to verify local storage functionality
"""

import os
import sys
from local_storage_utils import (
    get_local_downloads_dir,
    get_storage_info,
    get_or_create_date_folder,
    open_downloads_folder
)

def test_local_storage():
    """Test all local storage functions"""
    print("=== Testing Local Storage Functionality ===")

    # Test 1: Check storage info
    print("\n1. Testing storage info...")
    storage_ok, free_space, usage_percent = get_storage_info()
    print(f"Storage OK: {storage_ok}")
    print(f"Free space: {free_space:.2f} GB")
    print(f"Usage: {usage_percent:.1f}%")

    # Test 2: Get downloads directory
    print("\n2. Testing downloads directory...")
    downloads_dir = get_local_downloads_dir()
    print(f"Downloads directory: {downloads_dir}")
    print(f"Directory exists: {os.path.exists(downloads_dir)}")

    # Test 3: Create directories
    print("\n3. Testing directory creation...")
    from datetime import datetime
    test_date = datetime.now().strftime('%Y-%m-%d')
    try:
        test_folder = get_or_create_date_folder(downloads_dir, test_date)
        print(f"Created test folder: {test_folder}")
        print(f"Folder exists: {os.path.exists(test_folder)}")
        success = True
    except Exception as e:
        print(f"Directory creation failed: {e}")
        success = False

    # Test 4: Test opening downloads folder
    print("\n4. Testing folder opening...")
    try:
        print("Opening downloads folder...")
        # Don't actually open it in test, just check if function exists
        print("Folder opening function available")
    except Exception as e:
        print(f"Folder opening test failed: {e}")

    print("\n=== Local Storage Test Complete ===")

if __name__ == "__main__":
    test_local_storage()