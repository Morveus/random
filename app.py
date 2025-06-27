import os
import random
import hashlib
from pathlib import Path
from typing import List, Set
import logging
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

RANDOMNESS_SOURCE = Path("/randomness-source")
APP_PORT = int(os.getenv("APP_PORT", "5000"))
SPECIAL_CHARS = os.getenv("SPECIAL_CHARS", "!@#$%^&*()_+-=[]{}|;:,.<>?")
MAX_STRING_LENGTH = int(os.getenv("MAX_STRING_LENGTH", "256"))
MAX_STRINGS_PER_REQUEST = int(os.getenv("MAX_STRINGS_PER_REQUEST", "100"))

class RandomStringGenerator:
    def __init__(self):
        self.used_files: Set[str] = set()
    
    def get_random_snapshot(self) -> Path:
        """Get a random snapshot file from the source directory."""
        if not RANDOMNESS_SOURCE.exists():
            raise Exception(f"Randomness source directory {RANDOMNESS_SOURCE} does not exist")
        
        available_files = [
            f for f in RANDOMNESS_SOURCE.glob("*") 
            if f.is_file() and f.name not in self.used_files
        ]
        
        if not available_files:
            raise Exception("No available snapshot files")
        
        selected_file = random.choice(available_files)
        self.used_files.add(selected_file.name)
        return selected_file
    
    def generate_random_string(self, length: int, char_types: List[str]) -> str:
        """Generate a random string using snapshot data as entropy."""
        snapshot_file = self.get_random_snapshot()
        
        try:
            with open(snapshot_file, 'rb') as f:
                snapshot_data = f.read()
            
            # Generate seed from snapshot data
            hash_obj = hashlib.sha256(snapshot_data)
            seed = int.from_bytes(hash_obj.digest(), 'big')
            
            # Build character set
            charset = ""
            if "uppercase" in char_types:
                charset += "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
            if "lowercase" in char_types:
                charset += "abcdefghijklmnopqrstuvwxyz"
            if "numbers" in char_types:
                charset += "0123456789"
            if "special" in char_types:
                charset += SPECIAL_CHARS
            
            if not charset:
                raise ValueError("At least one character type must be selected")
            
            # Generate random string
            rng = random.Random(seed)
            result = ''.join(rng.choice(charset) for _ in range(length))
            
            # Delete used snapshot
            snapshot_file.unlink()
            logger.info(f"Used and deleted snapshot: {snapshot_file.name}")
            
            return result
            
        except Exception as e:
            logger.error(f"Error generating random string: {e}")
            raise
    
    def generate_passphrase(self, word_count: int, capitalize_words: bool, 
                          separate_with_dashes: bool, add_digit: bool) -> str:
        """Generate a passphrase using snapshot data as entropy."""
        # Load wordlist
        wordlist_path = Path(__file__).parent / "wordlist.txt"
        if not wordlist_path.exists():
            raise Exception("Wordlist file not found")
        
        with open(wordlist_path, 'r') as f:
            words = [line.strip() for line in f if line.strip()]
        
        if not words:
            raise Exception("Empty wordlist")
        
        snapshot_file = self.get_random_snapshot()
        
        try:
            with open(snapshot_file, 'rb') as f:
                snapshot_data = f.read()
            
            # Generate seed from snapshot data
            hash_obj = hashlib.sha256(snapshot_data)
            seed = int.from_bytes(hash_obj.digest(), 'big')
            
            # Generate passphrase
            rng = random.Random(seed)
            selected_words = []
            
            for i in range(word_count):
                word = rng.choice(words)
                
                # Add digit to one of the words if requested
                if add_digit and i == rng.randint(0, word_count - 1):
                    digit = str(rng.randint(0, 9))
                    word += digit
                    add_digit = False  # Only add one digit
                
                # Capitalize if requested
                if capitalize_words:
                    word = word.capitalize()
                
                selected_words.append(word)
            
            # Join with appropriate separator
            separator = '-' if separate_with_dashes else ' '
            passphrase = separator.join(selected_words)
            
            # Delete used snapshot
            snapshot_file.unlink()
            logger.info(f"Used and deleted snapshot: {snapshot_file.name}")
            
            return passphrase
            
        except Exception as e:
            logger.error(f"Error generating passphrase: {e}")
            raise

generator = RandomStringGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/generate', methods=['POST'])
def generate():
    try:
        data = request.json
        length = int(data.get('length', 16))
        count = int(data.get('count', 1))
        char_types = data.get('charTypes', [])
        
        # Validate inputs
        if length < 1 or length > MAX_STRING_LENGTH:
            return jsonify({'error': f'Length must be between 1 and {MAX_STRING_LENGTH}'}), 400
        
        # Check available snapshots for dynamic limit
        available_snapshots = len(list(RANDOMNESS_SOURCE.glob("*")))
        max_allowed = min(available_snapshots, MAX_STRINGS_PER_REQUEST)
        
        if count < 1 or count > max_allowed:
            return jsonify({'error': f'Count must be between 1 and {max_allowed} (limited by available snapshots)'}), 400
        
        if not char_types:
            return jsonify({'error': 'At least one character type must be selected'}), 400
        
        # Generate strings
        results = []
        for _ in range(count):
            random_string = generator.generate_random_string(length, char_types)
            results.append(random_string)
        
        return jsonify({'strings': results})
        
    except Exception as e:
        logger.error(f"Error in generate endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/generate-passphrase', methods=['POST'])
def generate_passphrase():
    try:
        data = request.json
        word_count = int(data.get('wordCount', 4))
        capitalize_words = bool(data.get('capitalizeWords', True))
        separate_with_dashes = bool(data.get('separateWithDashes', False))
        add_digit = bool(data.get('addDigit', False))
        
        # Validate inputs
        if word_count < 3 or word_count > 12:
            return jsonify({'error': 'Word count must be between 3 and 12'}), 400
        
        # Generate passphrase
        passphrase = generator.generate_passphrase(
            word_count, capitalize_words, separate_with_dashes, add_digit
        )
        
        return jsonify({'passphrase': passphrase})
        
    except Exception as e:
        logger.error(f"Error in generate-passphrase endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/health')
def health():
    try:
        snapshot_count = len(list(RANDOMNESS_SOURCE.glob("*")))
        return jsonify({
            'status': 'healthy',
            'available_snapshots': snapshot_count
        })
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=False)