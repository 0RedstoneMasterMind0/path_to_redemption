requirements = ['firebase_admin', 'cryptography']
import os, sys

for requirement in requirements:
    try:
        __import__(requirement)
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install {requirement}')

import os
import json
import sqlite3
import firebase_admin
from firebase_admin import credentials, firestore
from cryptography.fernet import Fernet
from datetime import datetime
from google.cloud.firestore_v1.base_document import DocumentSnapshot
from google.cloud.firestore_v1._helpers import DatetimeWithNanoseconds


class OnlineDatabase:
    def __init__(self, collection_name="entity_data", firebase_config_path="_data/access.json", encryption_key=None, database_path = "local.db"):
        """
        Initialize Firebase encrypted dictionary storage with local JSON table fallback

        Args:
            collection_name (str): Name of the Firestore collection (also used as table name)
            firebase_config_path (str): Path to Firebase service account JSON file
            encryption_key (str/bytes): Encryption key for online data
        """
        self.collection_name = collection_name
        self.firebase_config_path = firebase_config_path
        self.database_path = database_path
        self.use_firebase = False
        self.cipher = self.init_encryption(encryption_key)

        # Try Firebase first
        try:
            self.init_firebase()
            self.use_firebase = True
            print(f"✓ Using Firebase (encrypted) - collection: {collection_name}")
        except Exception as e:
            print(f"✗ Firebase unavailable: {e}")
            self.init_local_db()
            print(f"✓ Using local database table: {collection_name}")

    def init_firebase(self):
        """Initialize Firebase connection"""
        if not firebase_admin._apps:
            cred = credentials.Certificate(self.firebase_config_path)
            firebase_admin.initialize_app(cred)
        self.db = firestore.client()

    def init_local_db(self):
        """Initialize local SQLite database with single table"""
        self.local_conn = sqlite3.connect(self.database_path, check_same_thread=False)

        # Create single table with collection name
        self.local_conn.execute(f'''
            CREATE TABLE IF NOT EXISTS {self.collection_name} (
                id TEXT PRIMARY KEY,
                data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        self.local_conn.commit()

    def init_encryption(self, key):
        """Initialize encryption cipher"""
        if isinstance(key, str) and key:
            key = key.encode()
        return Fernet(key) if key else None

    def encrypt_data(self, data):
        """Encrypt dictionary data"""
        json_str = json.dumps(data, indent=2, default=self.json_serializer)
        encrypted = self.cipher.encrypt(json_str.encode())
        return encrypted.decode()

    def decrypt_data(self, encrypted_data):
        """Decrypt data back to dictionary"""
        decrypted = self.cipher.decrypt(encrypted_data.encode())
        return json.loads(decrypted.decode())

    def json_serializer(self, obj):
        """Custom JSON serializer to handle Firebase timestamp objects"""
        if isinstance(obj, DatetimeWithNanoseconds):
            return obj.isoformat()
        elif isinstance(obj, datetime):
            return obj.isoformat()
        elif hasattr(obj, 'timestamp'):
            # Handle other timestamp-like objects
            return datetime.fromtimestamp(obj.timestamp()).isoformat()
        else:
            # For any other non-serializable object, convert to string
            return str(obj)

    def sanitize_firebase_data(self, data):
        """Recursively sanitize Firebase data for JSON serialization"""
        if isinstance(data, dict):
            return {key: self.sanitize_firebase_data(value) for key, value in data.items()}
        elif isinstance(data, list):
            return [self.sanitize_firebase_data(item) for item in data]
        elif isinstance(data, DatetimeWithNanoseconds):
            return data.isoformat()
        elif isinstance(data, datetime):
            return data.isoformat()
        elif hasattr(data, 'timestamp'):
            return datetime.fromtimestamp(data.timestamp()).isoformat()
        else:
            return data

    def get(self, id_key):
        """Get dictionary by ID - tries Firebase first, falls back to local"""
        try:
            if self.use_firebase:
                # Try Firebase first
                try:
                    result = self._get_firebase(id_key)
                    if result is not None:
                        return result
                except Exception as e:
                    print(f"⚠️ Firebase get failed for '{id_key}': {e}")
                    # Fall back to local
                    if hasattr(self, 'local_conn'):
                        print(f"🔄 Falling back to local for '{id_key}'")
                        return self._get_local(id_key)
                    return None
            else:
                return self._get_local(id_key)
        except Exception as e:
            print(f"Error getting '{id_key}': {e}")
            return None

    def _get_firebase(self, id_key):
        """Get encrypted data from Firebase"""
        doc_ref = self.db.collection(self.collection_name).document(id_key)
        doc = doc_ref.get()

        if doc.exists:
            doc_data = doc.to_dict()
            encrypted_content = doc_data.get('encrypted_data')
            if encrypted_content:
                return self.decrypt_data(encrypted_content)
        return None

    def _get_local(self, id_key):
        """Get data from local table"""
        if not hasattr(self, 'local_conn'):
            return None

        cursor = self.local_conn.execute(f'SELECT data FROM {self.collection_name} WHERE id = ?', (id_key,))
        row = cursor.fetchone()

        if row:
            json_data = row[0]
            return json.loads(json_data)
        return None

    def set(self, id_key, dictionary):
        """Store dictionary with given ID - tries Firebase first, falls back to local"""
        try:
            if self.use_firebase:
                # Try Firebase first
                try:
                    result = self._set_firebase(id_key, dictionary)
                    if result:
                        # Also update local backup if available
                        if hasattr(self, 'local_conn'):
                            try:
                                self._set_local(id_key, dictionary)
                            except Exception as e:
                                print(f"⚠️ Local backup update failed for '{id_key}': {e}")
                        return True
                except Exception as e:
                    print(f"⚠️ Firebase set failed for '{id_key}': {e}")
                    # Fall back to local
                    if hasattr(self, 'local_conn'):
                        print(f"🔄 Falling back to local for '{id_key}'")
                        return self._set_local(id_key, dictionary)
                    return False
            else:
                return self._set_local(id_key, dictionary)
        except Exception as e:
            print(f"Error setting '{id_key}': {e}")
            return False

    def _set_firebase(self, id_key, dictionary):
        """Store encrypted data in Firebase"""
        encrypted_data = self.encrypt_data(dictionary)
        doc_data = {
            'encrypted_data': encrypted_data,
            'id': id_key,
            'updated_at': firestore.SERVER_TIMESTAMP
        }

        doc_ref = self.db.collection(self.collection_name).document(id_key)
        doc_ref.set(doc_data)
        print(f"✓ Stored encrypted: {id_key}")
        return True

    def _set_local(self, id_key, dictionary):
        """Store data as JSON in local table"""
        if not hasattr(self, 'local_conn'):
            return False

        json_data = json.dumps(dictionary, indent=2, default=self.json_serializer)

        self.local_conn.execute(f'''
            INSERT OR REPLACE INTO {self.collection_name} (id, data, updated_at) 
            VALUES (?, ?, CURRENT_TIMESTAMP)
        ''', (id_key, json_data))

        self.local_conn.commit()
        print(f"✓ Stored in local table {self.collection_name}: {id_key}")
        return True

    def list_all(self):
        """List all stored entity IDs - tries Firebase first, falls back to local"""
        try:
            if self.use_firebase:
                try:
                    return self._list_firebase()
                except Exception as e:
                    print(f"⚠️ Firebase list failed: {e}")
                    # Fall back to local
                    if hasattr(self, 'local_conn'):
                        print("🔄 Falling back to local for listing")
                        return self._list_local()
                    return []
            else:
                return self._list_local()
        except Exception as e:
            print(f"Error listing entities: {e}")
            return []

    def _list_firebase(self):
        """List all document IDs from Firebase"""
        docs = self.db.collection(self.collection_name).stream()
        return [doc.id for doc in docs]

    def _list_local(self):
        """List all entity IDs from local table"""
        if not hasattr(self, 'local_conn'):
            return []

        cursor = self.local_conn.execute(f'SELECT id FROM {self.collection_name}')
        return [row[0] for row in cursor.fetchall()]

    def _ensure_table_schema(self, table_name):
        """Ensure table has the correct schema, recreating if necessary"""
        if not hasattr(self, 'local_conn'):
            self.local_conn = sqlite3.connect(self.database_path, check_same_thread=False)

        try:
            # Check if table exists and get its schema
            cursor = self.local_conn.execute(f"PRAGMA table_info({table_name})")
            columns = cursor.fetchall()

            # Expected columns: id, data, updated_at
            expected_columns = {'id', 'data', 'updated_at'}
            existing_columns = {col[1] for col in columns}  # col[1] is column name

            # If table doesn't exist or has wrong schema, recreate it
            if not columns or not expected_columns.issubset(existing_columns):
                print(f"🔧 Recreating table {table_name} with correct schema")

                # Drop and recreate table
                self.local_conn.execute(f'DROP TABLE IF EXISTS {table_name}')
                self.local_conn.execute(f'''
                    CREATE TABLE {table_name} (
                        id TEXT PRIMARY KEY,
                        data TEXT,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                ''')
                self.local_conn.commit()
                print(f"✓ Table {table_name} recreated successfully")

        except Exception as e:
            print(f"⚠️ Error ensuring table schema for {table_name}: {e}")
            # Try to create table anyway
            self.local_conn.execute(f'''
                CREATE TABLE IF NOT EXISTS {table_name} (
                    id TEXT PRIMARY KEY,
                    data TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            self.local_conn.commit()

    def sync_all_collections_to_local(self):
        """
        Sync ALL Firebase collections as local tables for backup/fallback
        Creates local copies but keeps Firebase as primary
        """
        if not self.use_firebase:
            print("✗ Firebase not available - cannot sync collections")
            return False

        try:
            print("🔄 Starting sync of all Firebase collections to local backup...")

            # Get all collection names
            collections = self.db.collections()
            collection_names = [col.id for col in collections]

            if not collection_names:
                print("ℹ️ No collections found in Firebase")
                return True

            # Initialize local connection if not exists
            if not hasattr(self, 'local_conn'):
                self.local_conn = sqlite3.connect(self.database_path, check_same_thread=False)

            synced_count = 0

            for collection_name in collection_names:
                print(f"📋 Syncing collection: {collection_name}")

                # Ensure table has correct schema
                self._ensure_table_schema(collection_name)

                # Get all documents from this collection
                docs = self.db.collection(collection_name).stream()
                doc_count = 0

                for doc in docs:
                    try:
                        doc_data = doc.to_dict()

                        # Extract the actual data (decrypt if encrypted)
                        if 'encrypted_data' in doc_data:
                            try:
                                actual_data = self.decrypt_data(doc_data['encrypted_data'])
                            except Exception as e:
                                print(f"⚠️ Could not decrypt {doc.id} in {collection_name}: {e}")
                                continue
                        else:
                            # Raw data (not encrypted) - sanitize for JSON serialization
                            actual_data = {k: v for k, v in doc_data.items() if k not in ['id', 'updated_at']}
                            actual_data = self.sanitize_firebase_data(actual_data)

                        # Store in local table with proper JSON serialization
                        json_data = json.dumps(actual_data, indent=2, default=self.json_serializer)
                        self.local_conn.execute(f'''
                            INSERT OR REPLACE INTO {collection_name} (id, data, updated_at) 
                            VALUES (?, ?, CURRENT_TIMESTAMP)
                        ''', (doc.id, json_data))

                        doc_count += 1

                    except Exception as e:
                        print(f"⚠️ Error processing document {doc.id} in {collection_name}: {e}")
                        continue

                self.local_conn.commit()
                print(f"✅ Synced {doc_count} documents from {collection_name}")
                synced_count += 1

            print(f"🎉 Successfully synced {synced_count} collections to local backup")
            print("ℹ️ Firebase remains primary - local acts as fallback")

            return True

        except Exception as e:
            print(f"❌ Error syncing collections: {e}")
            return False

    def sync_all_collections_to_online(self):
        """
        Sync ALL local tables to Firebase collections
        Uploads local data to Firebase with encryption
        """
        if not self.use_firebase:
            print("✗ Firebase not available - cannot sync to online")
            return False

        if not hasattr(self, 'local_conn'):
            print("✗ Local database not available - nothing to sync")
            return False

        try:
            print("🔄 Starting sync of all local tables to Firebase...")

            # Get all local table names
            cursor = self.local_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            )
            table_names = [row[0] for row in cursor.fetchall()]

            if not table_names:
                print("ℹ️ No tables found in local database")
                return True

            synced_count = 0

            for table_name in table_names:
                print(f"📤 Syncing table: {table_name}")

                # Get all records from this table
                cursor = self.local_conn.execute(f'SELECT id, data FROM {table_name}')
                records = cursor.fetchall()
                doc_count = 0

                for record_id, json_data in records:
                    try:
                        # Parse the JSON data
                        actual_data = json.loads(json_data)

                        # Encrypt and store in Firebase
                        encrypted_data = self.encrypt_data(actual_data)
                        doc_data = {
                            'encrypted_data': encrypted_data,
                            'id': record_id,
                            'updated_at': firestore.SERVER_TIMESTAMP
                        }

                        # Store in Firebase collection
                        doc_ref = self.db.collection(table_name).document(record_id)
                        doc_ref.set(doc_data)

                        doc_count += 1

                    except Exception as e:
                        print(f"⚠️ Error processing record {record_id} in {table_name}: {e}")
                        continue

                print(f"✅ Synced {doc_count} documents to Firebase collection {table_name}")
                synced_count += 1

            print(f"🎉 Successfully synced {synced_count} local tables to Firebase")
            print("ℹ️ All local data uploaded to Firebase with encryption")

            return True

        except Exception as e:
            print(f"❌ Error syncing to Firebase: {e}")
            return False

    def sync_specific_collection_to_online(self, collection_name):
        """
        Sync a specific local table to Firebase collection

        Args:
            collection_name (str): Name of the collection/table to sync
        """
        if not self.use_firebase:
            print("✗ Firebase not available - cannot sync to online")
            return False

        if not hasattr(self, 'local_conn'):
            print("✗ Local database not available - nothing to sync")
            return False

        try:
            print(f"🔄 Syncing local table '{collection_name}' to Firebase...")

            # Check if table exists
            cursor = self.local_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
                (collection_name,)
            )
            if not cursor.fetchone():
                print(f"✗ Table '{collection_name}' not found in local database")
                return False

            # Get all records from this table
            cursor = self.local_conn.execute(f'SELECT id, data FROM {collection_name}')
            records = cursor.fetchall()
            doc_count = 0

            for record_id, json_data in records:
                try:
                    # Parse the JSON data
                    actual_data = json.loads(json_data)

                    # Encrypt and store in Firebase
                    encrypted_data = self.encrypt_data(actual_data)
                    doc_data = {
                        'encrypted_data': encrypted_data,
                        'id': record_id,
                        'updated_at': firestore.SERVER_TIMESTAMP
                    }

                    # Store in Firebase collection
                    doc_ref = self.db.collection(collection_name).document(record_id)
                    doc_ref.set(doc_data)

                    doc_count += 1

                except Exception as e:
                    print(f"⚠️ Error processing record {record_id} in {collection_name}: {e}")
                    continue

            print(f"✅ Synced {doc_count} documents to Firebase collection {collection_name}")
            return True

        except Exception as e:
            print(f"❌ Error syncing {collection_name} to Firebase: {e}")
            return False

    def sync_bidirectional(self, prefer_online=True):
        """
        Perform bidirectional sync between local and Firebase

        Args:
            prefer_online (bool): If True, Firebase data takes precedence for conflicts
                                If False, local data takes precedence
        """
        if not self.use_firebase:
            print("✗ Firebase not available - cannot perform bidirectional sync")
            return False

        if not hasattr(self, 'local_conn'):
            print("✗ Local database not available - cannot perform bidirectional sync")
            return False

        try:
            print("🔄 Starting bidirectional sync...")

            if prefer_online:
                print("📥 Priority: Firebase → Local (Firebase data takes precedence)")
                # Sync Firebase to local first
                firebase_success = self.sync_all_collections_to_local()

                # Then sync any local-only data to Firebase
                print("📤 Uploading local-only data to Firebase...")
                local_success = self.sync_all_collections_to_online()

            else:
                print("📤 Priority: Local → Firebase (Local data takes precedence)")
                # Sync local to Firebase first
                local_success = self.sync_all_collections_to_online()

                # Then sync any Firebase-only data to local
                print("📥 Downloading Firebase-only data to local...")
                firebase_success = self.sync_all_collections_to_local()

            if firebase_success and local_success:
                print("🎉 Bidirectional sync completed successfully!")
                return True
            else:
                print("⚠️ Bidirectional sync completed with some errors")
                return False

        except Exception as e:
            print(f"❌ Error during bidirectional sync: {e}")
            return False

    def get_collection_stats(self):
        """Get statistics about all collections/tables"""
        if self.use_firebase:
            return self._get_firebase_stats()
        else:
            return self._get_local_stats()

    def _get_firebase_stats(self):
        """Get Firebase collection statistics"""
        try:
            collections = self.db.collections()
            stats = {}

            for collection in collections:
                docs = list(self.db.collection(collection.id).stream())
                stats[collection.id] = {
                    'count': len(docs),
                    'type': 'firebase_encrypted'
                }

            return stats
        except Exception as e:
            print(f"Error getting Firebase stats: {e}")
            return {}

    def _get_local_stats(self):
        """Get local table statistics"""
        if not hasattr(self, 'local_conn'):
            return {}

        try:
            cursor = self.local_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name != 'sqlite_sequence'"
            )
            tables = [row[0] for row in cursor.fetchall()]

            stats = {}
            for table in tables:
                cursor = self.local_conn.execute(f'SELECT COUNT(*) FROM {table}')
                count = cursor.fetchone()[0]
                stats[table] = {
                    'count': count,
                    'type': 'local_backup'
                }

            return stats
        except Exception as e:
            print(f"Error getting local stats: {e}")
            return {}

    def reset_local_database(self):
        """Reset/clear the local database - useful for testing"""
        if hasattr(self, 'local_conn'):
            self.local_conn.close()

        # Remove the database file
        if os.path.exists(self.database_path):
            os.remove(self.database_path)
            print("🗑️ Local database reset")

        # Reinitialize
        self.init_local_db()


# Factory function to create database instances for any collection
def create_database(collection_name, firebase_config_path="_data/access.json", encryption_key=None):
    """
    Factory function to create database instances for any collection

    Args:
        collection_name (str): Name of the collection/table
        firebase_config_path (str): Path to Firebase config
        encryption_key (str/bytes): Encryption key

    Returns:
        OnlineDatabase: Database instance for the specified collection
    """
    return OnlineDatabase(collection_name, firebase_config_path, encryption_key)
