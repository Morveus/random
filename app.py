import os
import hashlib
import threading
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
        self._lock = threading.Lock()
        self.wordlist_path = Path(__file__).parent / "wordlist.txt"
    
    def get_random_snapshot_deterministic(self) -> Path:
        """Get snapshot file using deterministic selection (oldest first)."""
        if not RANDOMNESS_SOURCE.exists():
            raise Exception(f"Randomness source directory {RANDOMNESS_SOURCE} does not exist")
        
        available_files = [
            f for f in RANDOMNESS_SOURCE.glob("*") 
            if f.is_file() and f.name not in self.used_files
        ]
        
        if not available_files:
            raise Exception("No available snapshot files")
        
        # Sort by modification time for deterministic selection (oldest first)
        available_files.sort(key=lambda x: x.stat().st_mtime)
        selected_file = available_files[0]
        self.used_files.add(selected_file.name)
        return selected_file
    
    def _build_charset(self, char_types: List[str]) -> str:
        """Build character set from requested types."""
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
        
        return charset
    
    def generate_entropy_pool(self, required_bytes: int) -> bytes:
        """Generate sufficient entropy pool for the requested output length."""
        entropy_pool = b''
        
        while len(entropy_pool) < required_bytes:
            snapshot_file = self.get_random_snapshot_deterministic()
            
            with open(snapshot_file, 'rb') as f:
                snapshot_data = f.read()
            
            # Hash and append to pool
            entropy_chunk = hashlib.sha256(snapshot_data).digest()
            entropy_pool += entropy_chunk
            
            # Delete used snapshot
            snapshot_file.unlink()
            logger.info(f"Used and deleted snapshot: {snapshot_file.name}")
        
        return entropy_pool[:required_bytes]
    
    def generate_random_string(self, length: int, char_types: List[str]) -> str:
        """Generate a random string using snapshot data as entropy."""
        with self._lock:
            try:
                # Build character set
                charset = self._build_charset(char_types)
                
                # Use single snapshot for strings up to 64 characters (256 bits / 4 bits per char)
                # For longer strings, use entropy pooling
                if length <= 64:
                    snapshot_file = self.get_random_snapshot_deterministic()
                    
                    with open(snapshot_file, 'rb') as f:
                        snapshot_data = f.read()
                    
                    # Use full SHA256 output as entropy
                    entropy_pool = hashlib.sha256(snapshot_data).digest()
                    
                    # Delete used snapshot
                    snapshot_file.unlink()
                    logger.info(f"Used and deleted snapshot: {snapshot_file.name}")
                else:
                    # For very long strings, use entropy pooling
                    entropy_needed = ((length - 1) // 64 + 1) * 32  # 32 bytes per 64 chars
                    entropy_pool = self.generate_entropy_pool(entropy_needed)
                
                # Generate string using entropy pool
                result = []
                for i in range(length):
                    # Use 4 bits per character (enough for most charsets)
                    bit_offset = i * 4
                    byte_index = bit_offset // 8
                    bit_in_byte = bit_offset % 8
                    
                    # Extract 4 bits starting at bit_offset
                    if byte_index < len(entropy_pool):
                        if bit_in_byte <= 4:  # Can get 4 bits from this byte
                            entropy_bits = (entropy_pool[byte_index] >> (4 - bit_in_byte)) & 0xF
                        else:  # Need bits from two bytes
                            if byte_index + 1 < len(entropy_pool):
                                entropy_bits = ((entropy_pool[byte_index] << (bit_in_byte - 4)) | 
                                              (entropy_pool[byte_index + 1] >> (12 - bit_in_byte))) & 0xF
                            else:
                                entropy_bits = (entropy_pool[byte_index] << (bit_in_byte - 4)) & 0xF
                        
                        char_index = entropy_bits % len(charset)
                        result.append(charset[char_index])
                    else:
                        # Fallback: use byte-level entropy
                        entropy_byte = entropy_pool[i % len(entropy_pool)]
                        char_index = entropy_byte % len(charset)
                        result.append(charset[char_index])
                
                return ''.join(result)
                
            except Exception as e:
                logger.error(f"Error generating random string: {e}")
                raise
    
    def generate_passphrase(self, word_count: int, capitalize_words: bool, 
                          separate_with_dashes: bool, add_digit: bool) -> str:
        """Generate a passphrase using snapshot data as entropy."""
        with self._lock:
            try:
                # Load wordlist
                if not self.wordlist_path.exists():
                    raise Exception("Wordlist file not found")
                
                with open(self.wordlist_path, 'r') as f:
                    words = [line.strip() for line in f if line.strip()]
                
                if not words:
                    raise Exception("Empty wordlist")
                
                # Use single snapshot for typical passphrase lengths (up to 8 words)
                # SHA256 provides 32 bytes = enough for 8 words * 4 bytes each
                if word_count <= 8:
                    snapshot_file = self.get_random_snapshot_deterministic()
                    
                    with open(snapshot_file, 'rb') as f:
                        snapshot_data = f.read()
                    
                    # Use full SHA256 output as entropy
                    entropy_pool = hashlib.sha256(snapshot_data).digest()
                    
                    # Delete used snapshot
                    snapshot_file.unlink()
                    logger.info(f"Used and deleted snapshot: {snapshot_file.name}")
                else:
                    # For very long passphrases, use entropy pooling
                    entropy_needed = word_count * 4 + (4 if add_digit else 0)
                    entropy_pool = self.generate_entropy_pool(entropy_needed)
                
                selected_words = []
                entropy_offset = 0
                digit_position = None
                
                # Determine digit position if needed
                if add_digit:
                    digit_entropy = entropy_pool[entropy_offset:entropy_offset+2]  # Only need 2 bytes
                    digit_position = int.from_bytes(digit_entropy, 'big') % word_count
                    entropy_offset += 2
                
                # Select words using entropy pool
                for i in range(word_count):
                    word_entropy = entropy_pool[entropy_offset:entropy_offset+3]  # 3 bytes per word
                    word_index = int.from_bytes(word_entropy, 'big') % len(words)
                    word = words[word_index]
                    
                    # Add digit to designated word
                    if add_digit and i == digit_position:
                        # Use 1 byte for digit selection
                        digit_byte = entropy_pool[entropy_offset + 3] if entropy_offset + 3 < len(entropy_pool) else entropy_pool[-1]
                        digit = str(digit_byte % 10)
                        word += digit
                    
                    # Capitalize if requested
                    if capitalize_words:
                        word = word.capitalize()
                    
                    selected_words.append(word)
                    entropy_offset += 3
                
                # Join with appropriate separator
                separator = '-' if separate_with_dashes else ' '
                return separator.join(selected_words)
                
            except Exception as e:
                logger.error(f"Error generating passphrase: {e}")
                raise

generator = RandomStringGenerator()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/string')
def string_page():
    """Generate and display a single 32-character random string"""
    try:
        # Fixed parameters for string page
        length = 32
        char_types = ['uppercase', 'lowercase', 'numbers']
        
        # Generate string
        random_string = generator.generate_random_string(length, char_types)
        
        return render_template('string.html', generated_string=random_string)
        
    except Exception as e:
        logger.error(f"Error in string page: {e}")
        return render_template('string.html', error=str(e))

@app.route('/passphrase')
def passphrase_page():
    """Generate and display a 3-word passphrase"""
    try:
        # Fixed parameters for passphrase page
        word_count = 3
        capitalize_words = True
        separate_with_dashes = True
        add_digit = True
        
        # Generate passphrase
        passphrase = generator.generate_passphrase(
            word_count, capitalize_words, separate_with_dashes, add_digit
        )
        
        return render_template('passphrase.html', generated_passphrase=passphrase)
        
    except Exception as e:
        logger.error(f"Error in passphrase page: {e}")
        return render_template('passphrase.html', error=str(e))

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

@app.route('/api/string')
def api_string():
    """API endpoint: Generate a single 32-character random string (A-Z, a-z, 0-9)"""
    try:
        # Fixed parameters for API endpoint
        length = 32
        char_types = ['uppercase', 'lowercase', 'numbers']
        
        # Generate string
        random_string = generator.generate_random_string(length, char_types)
        
        return jsonify({'string': random_string})
        
    except Exception as e:
        logger.error(f"Error in API string endpoint: {e}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/passphrase')
def api_passphrase():
    """API endpoint: Generate a 3-word passphrase, capitalized, with dashes and one digit"""
    try:
        # Fixed parameters for API endpoint
        word_count = 3
        capitalize_words = True
        separate_with_dashes = True
        add_digit = True
        
        # Generate passphrase
        passphrase = generator.generate_passphrase(
            word_count, capitalize_words, separate_with_dashes, add_digit
        )
        
        return jsonify({'passphrase': passphrase})
        
    except Exception as e:
        logger.error(f"Error in API passphrase endpoint: {e}")
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=APP_PORT, debug=False)