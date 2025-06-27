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
MAX_STRINGS_PER_REQUEST = int(os.getenv("MAX_STRINGS_PER_REQUEST", "10"))

class RandomStringGenerator:
    def __init__(self):
        self.used_files: Set[str] = set()
        self._lock = threading.Lock()
        self.wordlist_path = Path(__file__).parent / "wordlist.txt"
    
    def get_available_entropy_count(self) -> int:
        """Get count of available entropy sources."""
        if not RANDOMNESS_SOURCE.exists():
            return 0
        
        available_files = [
            f for f in RANDOMNESS_SOURCE.glob("*") 
            if f.is_file() and f.name not in self.used_files
        ]
        return len(available_files)

    def get_random_snapshot_deterministic(self) -> Path:
        """Get snapshot file using deterministic selection (oldest first)."""
        if not RANDOMNESS_SOURCE.exists():
            raise Exception(f"Randomness source directory {RANDOMNESS_SOURCE} does not exist")
        
        available_files = [
            f for f in RANDOMNESS_SOURCE.glob("*") 
            if f.is_file() and f.name not in self.used_files
        ]
        
        if not available_files:
            raise Exception("No available snapshot files - entropy pool exhausted")
        
        # Warn if entropy is running low
        if len(available_files) <= 5:
            logger.warning(f"Low entropy warning: only {len(available_files)} snapshots remaining")
        
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
    
    def _secure_random_choice(self, entropy_pool: bytes, offset: int, choices: int) -> tuple[int, int]:
        """
        Select a random index from 0 to choices-1 using rejection sampling to avoid modulo bias.
        Returns (selected_index, bytes_consumed).
        """
        if choices <= 1:
            return 0, 0
        
        # Calculate how many bits we need
        bits_needed = (choices - 1).bit_length()
        bytes_needed = (bits_needed + 7) // 8
        
        max_attempts = 100  # Prevent infinite loops
        for attempt in range(max_attempts):
            if offset + bytes_needed > len(entropy_pool):
                # Not enough entropy remaining, use what we have with modulo (fallback)
                remaining_bytes = len(entropy_pool) - offset
                if remaining_bytes > 0:
                    value = int.from_bytes(entropy_pool[offset:offset + remaining_bytes], 'big')
                    return value % choices, remaining_bytes
                else:
                    return 0, 0
            
            # Extract the needed bytes
            value = int.from_bytes(entropy_pool[offset:offset + bytes_needed], 'big')
            
            # Check if value is in valid range (rejection sampling)
            max_valid = (2 ** (bytes_needed * 8)) // choices * choices
            if value < max_valid:
                return value % choices, bytes_needed
            
            # Rejected, try next bytes
            offset += 1
            if offset >= len(entropy_pool):
                break
        
        # Fallback if we couldn't find a valid value
        final_byte = entropy_pool[min(offset, len(entropy_pool) - 1)]
        return final_byte % choices, 1

    def generate_random_string(self, length: int, char_types: List[str]) -> str:
        """Generate a random string using snapshot data as entropy."""
        with self._lock:
            try:
                # Build character set
                charset = self._build_charset(char_types)
                charset_size = len(charset)
                
                # Calculate entropy needed (more generous allocation)
                bytes_per_char = max(2, (charset_size - 1).bit_length() // 4)  # At least 2 bytes per char
                entropy_needed = length * bytes_per_char
                
                # Use single snapshot for moderate strings, entropy pooling for very long ones
                if entropy_needed <= 32:  # Single SHA256 output
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
                    entropy_pool = self.generate_entropy_pool(entropy_needed)
                
                # Generate string using secure selection
                result = []
                entropy_offset = 0
                
                for i in range(length):
                    char_index, bytes_consumed = self._secure_random_choice(
                        entropy_pool, entropy_offset, charset_size
                    )
                    result.append(charset[char_index])
                    entropy_offset += bytes_consumed
                    
                    # Ensure we don't run out of entropy
                    if entropy_offset >= len(entropy_pool):
                        break
                
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
                
                wordlist_size = len(words)
                
                # Calculate entropy needed (more generous allocation)
                bytes_per_word = max(3, (wordlist_size - 1).bit_length() // 4)  # At least 3 bytes per word
                entropy_needed = word_count * bytes_per_word + (4 if add_digit else 0)
                
                # Use single snapshot for moderate passphrases, entropy pooling for very long ones
                if entropy_needed <= 32:  # Single SHA256 output
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
                    entropy_pool = self.generate_entropy_pool(entropy_needed)
                
                selected_words = []
                entropy_offset = 0
                digit_position = None
                
                # Determine digit position if needed using secure selection
                if add_digit:
                    digit_position, bytes_consumed = self._secure_random_choice(
                        entropy_pool, entropy_offset, word_count
                    )
                    entropy_offset += bytes_consumed
                
                # Select words using secure selection
                for i in range(word_count):
                    word_index, bytes_consumed = self._secure_random_choice(
                        entropy_pool, entropy_offset, wordlist_size
                    )
                    word = words[word_index]
                    entropy_offset += bytes_consumed
                    
                    # Add digit to designated word
                    if add_digit and i == digit_position:
                        # Use secure selection for digit (0-9)
                        digit, digit_bytes_consumed = self._secure_random_choice(
                            entropy_pool, entropy_offset, 10
                        )
                        word += str(digit)
                        entropy_offset += digit_bytes_consumed
                    
                    # Capitalize if requested
                    if capitalize_words:
                        word = word.capitalize()
                    
                    selected_words.append(word)
                    
                    # Ensure we don't run out of entropy
                    if entropy_offset >= len(entropy_pool):
                        break
                
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
        
        # Enforce maximum limit
        if count < 1 or count > MAX_STRINGS_PER_REQUEST:
            return jsonify({'error': f'Count must be between 1 and {MAX_STRINGS_PER_REQUEST}'}), 400
        
        # Check if we have enough snapshots
        available_snapshots = len(list(RANDOMNESS_SOURCE.glob("*")))
        if count > available_snapshots:
            return jsonify({'error': f'Not enough entropy available. Requested {count}, but only {available_snapshots} snapshots available'}), 400
        
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
        available_snapshots = generator.get_available_entropy_count()
        total_snapshots = len(list(RANDOMNESS_SOURCE.glob("*")))
        
        status = 'healthy'
        if available_snapshots == 0:
            status = 'critical'
        elif available_snapshots <= 5:
            status = 'warning'
        
        return jsonify({
            'status': status,
            'available_snapshots': available_snapshots,
            'total_snapshots': total_snapshots,
            'used_snapshots': len(generator.used_files)
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