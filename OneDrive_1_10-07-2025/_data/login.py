requirements = ['firebase_admin', 'cryptography', 'tkinter']
import os, sys

for requirement in requirements:
    try:
        __import__(requirement)
    except ImportError:
        os.system(f'"{sys.executable}" -m pip install {requirement}')

import tkinter as tk
from tkinter import messagebox, simpledialog
import hashlib
import os
import time
import firebase_admin
from firebase_admin import credentials, firestore
from cryptography.fernet import Fernet
import json
import sqlite3


class FirebaseLoginApp:
    def __init__(self, firebase_config_path, encryption_key=None):
        self.set_fps = 120
        self.root = tk.Tk()
        self.root.title("Login System")
        self.root.overrideredirect(True)
        self.root.state('zoomed')
        self.root.configure(bg='#2c3e50')

        self.init_firebase(firebase_config_path)
        self.cipher = self.init_encryption(encryption_key)
        self.init_local_db()
        self.user_id = None
        self.fps_target = 60  # Default FPS target
        self.remember_me = False

        self.center_frame = tk.Frame(self.root, bg='#34495e', padx=40, pady=40)
        self.center_frame.place(relx=0.5, rely=0.5, anchor='center')
        self.create_widgets()

    def init_firebase(self, config_path):
        try:
            if not firebase_admin._apps:
                cred = credentials.Certificate(config_path)
                firebase_admin.initialize_app(cred)
            self.db = firestore.client()
        except Exception as e:
            messagebox.showerror("Firebase Error", f"Failed to connect to Firebase: {str(e)}")
            self.root.quit()

    def init_encryption(self, key=None):
        key_file = "keys/encryption.key"
        if key is None:
            if os.path.exists(key_file):
                try:
                    with open(key_file, 'rb') as f:
                        key = f.read()
                except:
                    key = Fernet.generate_key()
            else:
                key = Fernet.generate_key()
                try:
                    os.makedirs("keys", exist_ok=True)
                    with open(key_file, 'wb') as f:
                        f.write(key)
                except:
                    pass
        elif isinstance(key, str):
            key = key.encode()
        return Fernet(key)

    def init_local_db(self):
        """Initialize local SQLite database for storing remembered credentials"""
        try:
            os.makedirs("local_data", exist_ok=True)
            self.local_db_path = "local_data/remembered_user.db"

            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()

            # Create table if it doesn't exist
            cursor.execute('''
                           CREATE TABLE IF NOT EXISTS remembered_user
                           (
                               id
                               INTEGER
                               PRIMARY
                               KEY,
                               username_hash
                               TEXT
                               NOT
                               NULL,
                               password_hash
                               TEXT
                               NOT
                               NULL,
                               user_id
                               INTEGER
                               NOT
                               NULL,
                               fps_target
                               INTEGER
                               NOT
                               NULL,
                               encrypted_username
                               TEXT
                               NOT
                               NULL,
                               created_at
                               TIMESTAMP
                               DEFAULT
                               CURRENT_TIMESTAMP
                           )
                           ''')

            conn.commit()
            conn.close()

        except Exception as e:
            print(f"Failed to initialize local database: {e}")
            self.local_db_path = None

    def save_remembered_user(self, username_hash, password_hash, user_id, fps_target, encrypted_username):
        """Save user credentials to local database (only one user can be remembered)"""
        if not self.local_db_path:
            return False

        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()

            # Clear any existing remembered user (only one allowed)
            cursor.execute('DELETE FROM remembered_user')

            # Insert new remembered user
            cursor.execute('''
                           INSERT INTO remembered_user (username_hash, password_hash, user_id, fps_target, encrypted_username)
                           VALUES (?, ?, ?, ?, ?)
                           ''', (username_hash, password_hash, user_id, fps_target, encrypted_username))

            conn.commit()
            conn.close()
            return True

        except Exception as e:
            print(f"Failed to save remembered user: {e}")
            return False

    def get_remembered_user(self):
        """Get remembered user credentials from local database"""
        if not self.local_db_path:
            return None

        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()

            cursor.execute(
                'SELECT username_hash, password_hash, user_id, fps_target, encrypted_username FROM remembered_user LIMIT 1')
            result = cursor.fetchone()

            conn.close()

            if result:
                return {
                    'username_hash': result[0],
                    'password_hash': result[1],
                    'user_id': result[2],
                    'fps_target': result[3],
                    'encrypted_username': result[4]
                }
            return None

        except Exception as e:
            print(f"Failed to get remembered user: {e}")
            return None

    def clear_remembered_user(self):
        """Clear remembered user from local database"""
        if not self.local_db_path:
            return

        try:
            conn = sqlite3.connect(self.local_db_path)
            cursor = conn.cursor()
            cursor.execute('DELETE FROM remembered_user')
            conn.commit()
            conn.close()
        except Exception as e:
            print(f"Failed to clear remembered user: {e}")

    def encrypt_data(self, data):
        try:
            if isinstance(data, str):
                data = data.encode()
            elif isinstance(data, dict):
                data = json.dumps(data).encode()
            return self.cipher.encrypt(data).decode()
        except:
            return None

    def decrypt_data(self, encrypted_data):
        try:
            if not encrypted_data:
                return None
            if isinstance(encrypted_data, bytes):
                encrypted_data = encrypted_data.decode()

            decrypted = self.cipher.decrypt(encrypted_data.encode())
            try:
                return json.loads(decrypted.decode())
            except json.JSONDecodeError:
                return decrypted.decode()
        except:
            return None

    def create_widgets(self):
        # Title
        tk.Label(
            self.center_frame,
            text="Secure Login System",
            font=('Arial', 24, 'bold'),
            bg='#34495e',
            fg='white'
        ).pack(pady=(0, 30))

        # Username field
        tk.Label(
            self.center_frame,
            text="Username:",
            font=('Arial', 12),
            bg='#34495e',
            fg='white'
        ).pack(anchor='w', pady=(0, 5))

        self.username_entry = tk.Entry(
            self.center_frame,
            font=('Arial', 14),
            width=40,
            relief='flat',
            bd=5
        )
        self.username_entry.pack(pady=(0, 15))

        # Password field
        tk.Label(
            self.center_frame,
            text="Password:",
            font=('Arial', 12),
            bg='#34495e',
            fg='white'
        ).pack(anchor='w', pady=(0, 5))

        self.password_entry = tk.Entry(
            self.center_frame,
            font=('Arial', 14),
            width=40,
            show="*",
            relief='flat',
            bd=5
        )
        self.password_entry.pack(pady=(0, 15))

        # Remember Me checkbox
        self.remember_var = tk.BooleanVar()
        remember_frame = tk.Frame(self.center_frame, bg='#34495e')
        remember_frame.pack(pady=(0, 15))

        tk.Checkbutton(
            remember_frame,
            text="Remember Me",
            variable=self.remember_var,
            font=('Arial', 11),
            bg='#34495e',
            fg='white',
            selectcolor='#34495e',
            activebackground='#34495e',
            activeforeground='white'
        ).pack()

        # FPS Display
        self.fps_label = tk.Label(
            self.center_frame,
            text=f"FPS Target: {self.fps_target}",
            font=('Arial', 10),
            bg='#34495e',
            fg='#95a5a6'
        )
        self.fps_label.pack(pady=(0, 10))

        # Buttons
        button_frame = tk.Frame(self.center_frame, bg='#34495e')
        button_frame.pack(pady=10)

        tk.Button(
            button_frame,
            text="Login",
            command=self.login,
            font=('Arial', 12, 'bold'),
            bg='#27ae60',
            fg='white',
            width=12,
            relief='flat',
            cursor='hand2'
        ).pack(side='left', padx=(0, 10))

        tk.Button(
            button_frame,
            text="Use Local",
            command=self.use_local_login,
            font=('Arial', 12),
            bg='#9b59b6',
            fg='white',
            width=12,
            relief='flat',
            cursor='hand2'
        ).pack(side='left', padx=(0, 10))

        tk.Button(
            button_frame,
            text="New User",
            command=self.show_register,
            font=('Arial', 12),
            bg='#3498db',
            fg='white',
            width=12,
            relief='flat',
            cursor='hand2'
        ).pack(side='left', padx=(0, 10))

        tk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel,
            font=('Arial', 12),
            bg='#e74c3c',
            fg='white',
            width=12,
            relief='flat',
            cursor='hand2'
        ).pack(side='left')

        # Debug button frame
        debug_frame = tk.Frame(self.center_frame, bg='#34495e')
        debug_frame.pack(pady=(20, 0))

        tk.Button(
            debug_frame,
            text="Change FPS Target",
            command=self.change_fps_target,
            font=('Arial', 10),
            bg='#9b59b6',
            fg='white',
            width=15,
            relief='flat',
            cursor='hand2'
        ).pack()

        # Bind keys
        self.root.bind('<Return>', lambda event: self.login())
        self.root.bind('<Escape>', lambda event: self.cancel())
        self.root.bind('<Alt-F4>', lambda event: self.cancel())
        self.root.bind('<F12>', lambda event: self.change_fps_target())  # Debug hotkey
        self.username_entry.focus()

    def use_local_login(self):
        """Try to login using locally stored credentials"""
        remembered_user = self.get_remembered_user()

        if not remembered_user:
            messagebox.showinfo("No Remembered User",
                                "No locally stored credentials found. Please login normally first and check 'Remember Me'.")
            return

        try:
            # Decrypt the username for display
            decrypted_username = self.decrypt_data(remembered_user['encrypted_username'])

            # Set user data
            self.user_id = remembered_user['user_id']
            self.fps_target = remembered_user['fps_target']
            self.set_fps = remembered_user['fps_target']
            self.remember_me = True

            # Update FPS display
            self.fps_label.config(text=f"FPS Target: {self.fps_target}")

            if decrypted_username:
                messagebox.showinfo("Success", f"Welcome back, {decrypted_username}! (Local Login)")
            else:
                messagebox.showinfo("Success", "Welcome back! (Local Login)")

            self.root.quit()

        except Exception as e:
            messagebox.showerror("Error", f"Failed to use local login: {str(e)}")

    def change_fps_target(self):
        """Debug function to change FPS target"""
        try:
            new_fps = simpledialog.askinteger(
                "Change FPS Target",
                f"Current FPS Target: {self.fps_target}\n\nEnter new FPS target:",
                initialvalue=self.fps_target,
                minvalue=1,
                maxvalue=999
            )
            if new_fps is not None:
                self.fps_target = new_fps
                self.set_fps = new_fps
                self.fps_label.config(text=f"FPS Target: {self.fps_target}")
                messagebox.showinfo("Success", f"FPS target changed to {self.fps_target}")

                # If user is logged in, save the new FPS target to database
                if hasattr(self, 'current_username_hash'):
                    self.save_user_fps_target(self.current_username_hash)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to change FPS target: {str(e)}")

    def load_user_fps_target(self, username_hash):
        """Load user's saved FPS target preference"""
        try:
            user_data = self.get_user_data(username_hash)
            if user_data and 'fps_target' in user_data:
                self.fps_target = user_data['fps_target']
            else:
                # Old user without FPS target, keep default (60)
                self.fps_target = 60
            self.fps_label.config(text=f"FPS Target: {self.fps_target}")
        except Exception as e:
            print(f"Failed to load FPS target: {e}")
            self.fps_target = 60  # Fallback to default

    def save_user_fps_target(self, username_hash):
        """Save user's FPS target preference"""
        try:
            user_data = self.get_user_data(username_hash)
            if user_data:
                user_data['fps_target'] = self.fps_target
                self.save_user_data(username_hash, user_data)
        except Exception as e:
            print(f"Failed to save FPS target: {e}")

    def cancel(self):
        self.root.quit()
        self.root.destroy()

    def hash_username(self, username):
        username_clean = username.lower().strip()
        return hashlib.sha256(username_clean.encode()).hexdigest()

    def hash_password(self, password):
        salt = "your_app_salt_here_change_this_to_unique_value"
        return hashlib.sha256((password + salt).encode()).hexdigest()

    def get_user_data(self, username_hash):
        try:
            doc_ref = self.db.collection('users').document(username_hash)
            doc = doc_ref.get()
            return doc.to_dict() if doc.exists else None
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to retrieve user data: {str(e)}")
            return None

    def save_user_data(self, username_hash, data):
        try:
            doc_ref = self.db.collection('users').document(username_hash)
            doc_ref.set(data)
            return True
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to save user data: {str(e)}")
            return False

    def get_next_id(self):
        try:
            counter_ref = self.db.collection('metadata').document('user_counter')
            transaction = self.db.transaction()

            @firestore.transactional
            def update_counter(transaction, counter_ref):
                counter_doc = counter_ref.get(transaction=transaction)
                next_id = counter_doc.to_dict().get('last_id', 0) + 1 if counter_doc.exists else 1
                transaction.set(counter_ref, {'last_id': next_id})
                return next_id

            return update_counter(transaction, counter_ref)
        except Exception as e:
            messagebox.showerror("Database Error", f"Failed to get next ID: {str(e)}")
            return None

    def login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            messagebox.showerror("Error", "Please enter both username and password")
            return

        username_hash = self.hash_username(username)
        password_hash = self.hash_password(password)
        user_data = self.get_user_data(username_hash)

        if user_data is None:
            messagebox.showerror("Error", "Username not found")
            self.username_entry.delete(0, tk.END)
            self.password_entry.delete(0, tk.END)
            return

        if user_data.get('password_hash') == password_hash:
            self.user_id = user_data.get('user_id')
            self.current_username_hash = username_hash  # Store for FPS saving
            self.remember_me = self.remember_var.get()

            # Load user's FPS target preference, set default if not exists
            self.load_user_fps_target(username_hash)

            # If user doesn't have FPS target set (old user), set default and save
            if 'fps_target' not in user_data:
                user_data['fps_target'] = self.fps_target
                self.save_user_data(username_hash, user_data)

            encrypted_username = user_data.get('encrypted_username')

            # Handle remember me functionality
            if self.remember_me:
                if self.save_remembered_user(username_hash, password_hash, self.user_id, self.fps_target,
                                             encrypted_username):
                    remember_msg = " (Credentials saved locally)"
                else:
                    remember_msg = " (Failed to save credentials locally)"
            else:
                # Clear any existing remembered user if remember me is not checked
                self.clear_remembered_user()
                remember_msg = ""

            if encrypted_username:
                decrypted_username = self.decrypt_data(encrypted_username)
                if decrypted_username:
                    messagebox.showinfo("Success", f"Welcome back, {decrypted_username}!{remember_msg}")
                else:
                    messagebox.showinfo("Success", f"Welcome back!{remember_msg}")
            else:
                messagebox.showinfo("Success", f"Welcome back!{remember_msg}")

            # Save current FPS target preference
            self.save_user_fps_target(username_hash)

            self.root.quit()
        else:
            messagebox.showerror("Error", "Invalid password")
            self.password_entry.delete(0, tk.END)

    def show_register(self):
        reg_window = tk.Toplevel(self.root)
        reg_window.title("Register New User")
        reg_window.geometry("500x500")
        reg_window.configure(bg='#34495e')
        reg_window.transient(self.root)
        reg_window.grab_set()

        reg_window.geometry("+{}+{}".format(
            int(self.root.winfo_screenwidth() / 2 - 250),
            int(self.root.winfo_screenheight() / 2 - 250)
        ))

        main_frame = tk.Frame(reg_window, bg='#34495e')
        main_frame.pack(fill='both', expand=True, padx=20, pady=20)

        # Warning
        warning_frame = tk.Frame(main_frame, bg='#e74c3c', padx=10, pady=10)
        warning_frame.pack(fill='x', pady=(0, 20))

        tk.Label(warning_frame, text="⚠️ IMPORTANT WARNING ⚠️",
                 font=('Arial', 14, 'bold'), bg='#e74c3c', fg='white').pack()
        tk.Label(warning_frame, text="Once a password is forgotten, it CANNOT be recovered!",
                 font=('Arial', 11, 'bold'), bg='#e74c3c', fg='white').pack()
        tk.Label(warning_frame, text="Make sure to remember your password or write it down safely.",
                 font=('Arial', 11), bg='#e74c3c', fg='white').pack()

        tk.Label(main_frame, text="Register New User", font=('Arial', 16, 'bold'),
                 bg='#34495e', fg='white').pack(pady=(0, 20))

        # Form fields
        tk.Label(main_frame, text="Username:", font=('Arial', 12),
                 bg='#34495e', fg='white').pack(anchor='w')
        reg_username = tk.Entry(main_frame, font=('Arial', 14), width=45)
        reg_username.pack(pady=(5, 10))

        tk.Label(main_frame, text="Password:", font=('Arial', 12),
                 bg='#34495e', fg='white').pack(anchor='w')
        reg_password = tk.Entry(main_frame, font=('Arial', 14), width=45, show="*")
        reg_password.pack(pady=(5, 10))

        tk.Label(main_frame, text="Confirm Password:", font=('Arial', 12),
                 bg='#34495e', fg='white').pack(anchor='w')
        reg_confirm = tk.Entry(main_frame, font=('Arial', 14), width=45, show="*")
        reg_confirm.pack(pady=(5, 10))

        # FPS Target setting
        tk.Label(main_frame, text="Preferred FPS Target:", font=('Arial', 12),
                 bg='#34495e', fg='white').pack(anchor='w')
        fps_frame = tk.Frame(main_frame, bg='#34495e')
        fps_frame.pack(pady=(5, 20))

        fps_var = tk.StringVar(value="60")
        fps_entry = tk.Entry(fps_frame, font=('Arial', 12), width=10, textvariable=fps_var)
        fps_entry.pack(side='left')
        tk.Label(fps_frame, text="FPS (recommended: 60)", font=('Arial', 10),
                 bg='#34495e', fg='#95a5a6').pack(side='left', padx=(10, 0))

        def register_user():
            username = reg_username.get().strip()
            password = reg_password.get()
            confirm = reg_confirm.get()

            if not username or not password:
                messagebox.showerror("Error", "Please fill all required fields")
                return

            if password != confirm:
                messagebox.showerror("Error", "Passwords don't match")
                return

            # Validate FPS target
            try:
                fps_target = int(fps_var.get())
                if fps_target < 1 or fps_target > 999:
                    raise ValueError("FPS must be between 1 and 999")
            except ValueError:
                messagebox.showerror("Error", "Please enter a valid FPS target (1-999)")
                return

            username_hash = self.hash_username(username)

            if self.get_user_data(username_hash) is not None:
                messagebox.showerror("Error", "Username already exists")
                return

            new_id = self.get_next_id()
            if new_id is None:
                return

            encrypted_username = self.encrypt_data(username)
            if encrypted_username is None:
                messagebox.showerror("Error", "Failed to encrypt username")
                return

            user_data = {
                'user_id': new_id,
                'password_hash': self.hash_password(password),
                'encrypted_username': encrypted_username,
                'fps_target': fps_target,
                'created_at': firestore.SERVER_TIMESTAMP
            }

            if self.save_user_data(username_hash, user_data):
                self.user_id = new_id
                self.fps_target = fps_target
                self.set_fps = fps_target
                messagebox.showinfo("Success", f"User registered successfully! Welcome {username}!")
                reg_window.destroy()
                self.root.quit()

        btn_frame = tk.Frame(main_frame, bg='#34495e')
        btn_frame.pack(pady=20)

        tk.Button(btn_frame, text="Register", command=register_user,
                  bg='#27ae60', fg='white', font=('Arial', 12, 'bold'),
                  width=12, relief='flat', cursor='hand2').pack(side='left', padx=(0, 10))

        tk.Button(btn_frame, text="Cancel", command=reg_window.destroy,
                  bg='#e74c3c', fg='white', font=('Arial', 12),
                  width=10, relief='flat', cursor='hand2').pack(side='left')

        reg_username.focus()
        reg_window.bind('<Return>', lambda e: register_user())

    def close(self):
        time.sleep(2)
        self.root.destroy()

    def run(self):
        try:
            self.root.mainloop()
        finally:
            # Ensure proper cleanup
            try:
                if hasattr(self, 'root'):
                    self.root.destroy()
            except (tk.TclError, RuntimeError):
                pass  # Window already destroyed or thread issue

        # Return [user_id, fps_target, remember_me] instead of just user_id
        return [self.user_id, self.set_fps, self.remember_me] if self.user_id else None


def run_login_app(firebase_config_path="_data/access.json", encryption_key=None):
    """
    Run the login app with Firebase backend

    Args:
        firebase_config_path (str): Path to Firebase service account JSON file
        encryption_key (str, optional): Encryption key for sensitive data

    Returns:
        list or None: [user_id, fps_target, remember_me] if login successful, None if cancelled
    """
    app = FirebaseLoginApp(firebase_config_path, encryption_key)
    return app.run()