#!/usr/bin/env python3
"""
Helper script to verify Supabase password and test connection.
"""
import os
import sys
from dotenv import load_dotenv
import psycopg2

# Load environment variables
load_dotenv()

def test_password(password):
    """Test connection with a given password."""
    host = os.getenv('SUPABASE_HOST', 'db.vbhbkjiwcdfaoyqvfgim.supabase.co')
    port = os.getenv('SUPABASE_PORT', '5432')
    database = os.getenv('SUPABASE_DB', 'postgres')
    user = os.getenv('SUPABASE_USER', 'postgres')
    
    try:
        print(f"🔐 Testing password...")
        conn = psycopg2.connect(
            host=host,
            port=port,
            database=database,
            user=user,
            password=password,
            connect_timeout=5
        )
        
        # Quick test query
        cur = conn.cursor()
        cur.execute("SELECT current_database(), current_user, version();")
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        print(f"✅ SUCCESS! Connected to database: {result[0]}")
        print(f"   User: {result[1]}")
        print(f"   PostgreSQL: {result[2].split(',')[0]}")
        return True
        
    except psycopg2.OperationalError as e:
        error_msg = str(e)
        if "password authentication failed" in error_msg:
            print("❌ Password authentication failed - incorrect password")
        elif "timeout" in error_msg.lower():
            print("❌ Connection timeout - check network/firewall settings")
        else:
            print(f"❌ Connection error: {error_msg}")
        return False
    except Exception as e:
        print(f"❌ Error: {type(e).__name__}: {str(e)}")
        return False

def main():
    print("=" * 60)
    print("Supabase Password Verification")
    print("=" * 60)
    print()
    
    # Get current password from .env
    current_password = os.getenv('SUPABASE_PASSWORD', '')
    
    if not current_password or current_password == 'your-password-here':
        print("❌ No password found in .env file")
        print("\n💡 How to get your Supabase password:")
        print("   1. Go to https://supabase.com/dashboard")
        print("   2. Select your project")
        print("   3. Go to Settings → Database")
        print("   4. Look for 'Connection string' or 'Database password'")
        print("   5. Or reset password: Settings → Database → Reset database password")
        print("\n   The connection string format is:")
        print("   postgresql://postgres:[PASSWORD]@db.xxxxx.supabase.co:5432/postgres")
        return False
    
    print(f"📋 Testing password from .env file...")
    print(f"   Host: {os.getenv('SUPABASE_HOST')}")
    print(f"   User: {os.getenv('SUPABASE_USER')}")
    print(f"   Database: {os.getenv('SUPABASE_DB')}")
    print()
    
    if test_password(current_password):
        print("\n" + "=" * 60)
        print("✅ Password is CORRECT! Your connection is working.")
        print("=" * 60)
        return True
    else:
        print("\n" + "=" * 60)
        print("❌ Password verification FAILED")
        print("=" * 60)
        print("\n💡 Next steps to fix:")
        print("   1. Go to Supabase Dashboard: https://supabase.com/dashboard")
        print("   2. Select your project")
        print("   3. Navigate to: Settings → Database")
        print("   4. Find the 'Connection string' section")
        print("   5. Copy the password from the connection string")
        print("      Format: postgresql://postgres:[PASSWORD]@...")
        print("   6. Or click 'Reset database password' to set a new one")
        print("\n📝 After getting the correct password, update your .env:")
        print("   SUPABASE_PASSWORD=your-actual-password")
        print("   DATABASE_URL=postgresql://postgres:your-actual-password@db.vbhbkjiwcdfaoyqvfgim.supabase.co:5432/postgres")
        return False

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n👋 Cancelled.")
        sys.exit(1)
