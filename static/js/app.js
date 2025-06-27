document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('generatorForm');
    const passphraseForm = document.getElementById('passphraseForm');
    const lengthSlider = document.getElementById('lengthSlider');
    const lengthInput = document.getElementById('lengthInput');
    const countSlider = document.getElementById('countSlider');
    const countInput = document.getElementById('count');
    const countDisplay = document.getElementById('countDisplay');
    const wordCountSlider = document.getElementById('wordCountSlider');
    const wordCountInput = document.getElementById('wordCount');
    const wordCountDisplay = document.getElementById('wordCountDisplay');
    const resultsDiv = document.getElementById('results');
    const stringsList = document.getElementById('stringsList');
    const errorDiv = document.getElementById('error');
    const statusSpan = document.getElementById('status');
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabContents = document.querySelectorAll('.tab-content');

    // Sync slider and input for length
    lengthSlider.addEventListener('input', function() {
        lengthInput.value = this.value;
    });

    lengthInput.addEventListener('input', function() {
        lengthSlider.value = this.value;
    });

    // Sync slider and input for count
    countSlider.addEventListener('input', function() {
        countInput.value = this.value;
        countDisplay.textContent = this.value;
    });

    countInput.addEventListener('input', function() {
        countSlider.value = this.value;
        countDisplay.textContent = this.value;
    });

    // Sync slider and input for word count
    wordCountSlider.addEventListener('input', function() {
        wordCountInput.value = this.value;
        wordCountDisplay.textContent = this.value;
    });

    wordCountInput.addEventListener('input', function() {
        wordCountSlider.value = this.value;
        wordCountDisplay.textContent = this.value;
    });

    // Tab switching
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const targetTab = this.getAttribute('data-tab');
            
            // Clear results when switching tabs
            resultsDiv.classList.add('hidden');
            errorDiv.classList.add('hidden');
            
            // Update tab buttons
            tabButtons.forEach(btn => btn.classList.remove('active'));
            this.classList.add('active');
            
            // Update tab contents
            tabContents.forEach(content => {
                content.classList.remove('active');
                if (content.getAttribute('data-tab') === targetTab) {
                    content.classList.add('active');
                }
            });
        });
    });

    // Set current year
    document.getElementById('currentYear').textContent = new Date().getFullYear();

    // Load saved settings from localStorage
    loadSettings();

    // Save settings when they change
    setupSettingsSync();

    // Check system health
    checkHealth();
    setInterval(checkHealth, 500); // Check every 500ms for responsive updates

    // Form submission for random strings
    form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Clear previous results and errors
        resultsDiv.classList.add('hidden');
        errorDiv.classList.add('hidden');
        stringsList.innerHTML = '';

        // Get form data
        const length = parseInt(lengthInput.value);
        const count = parseInt(document.getElementById('count').value);
        const charTypes = Array.from(document.querySelectorAll('input[name="charType"]:checked'))
            .map(cb => cb.value);

        // Validate
        if (charTypes.length === 0) {
            showError('Please select at least one character type');
            return;
        }

        // Disable button during generation
        const submitBtn = form.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Generating...';

        try {
            const response = await fetch('/generate', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    length: length,
                    count: count,
                    charTypes: charTypes
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate strings');
            }

            // Display results
            displayResults(data.strings, 'Generated Strings');
            
        } catch (error) {
            showError(error.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Generate Random Strings';
        }
    });

    // Form submission for passphrase
    passphraseForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        // Clear previous results and errors
        resultsDiv.classList.add('hidden');
        errorDiv.classList.add('hidden');
        stringsList.innerHTML = '';

        // Get form data
        const wordCount = parseInt(wordCountInput.value);
        const capitalizeWords = document.getElementById('capitalizeWords').checked;
        const separateWithDashes = document.getElementById('separateWithDashes').checked;
        const addDigit = document.getElementById('addDigit').checked;

        // Disable button during generation
        const submitBtn = passphraseForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Generating...';

        try {
            const response = await fetch('/generate-passphrase', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    wordCount: wordCount,
                    capitalizeWords: capitalizeWords,
                    separateWithDashes: separateWithDashes,
                    addDigit: addDigit
                })
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Failed to generate passphrase');
            }

            // Display results
            displayResults([data.passphrase], 'Generated Passphrase');
            
        } catch (error) {
            showError(error.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Generate Passphrase';
        }
    });

    function displayResults(strings, title = 'Generated Strings') {
        resultsDiv.classList.remove('hidden');
        
        // Update results title
        const resultsTitle = document.querySelector('.results-title');
        resultsTitle.textContent = title;
        
        strings.forEach((string, index) => {
            const stringItem = document.createElement('div');
            stringItem.className = 'string-item';
            stringItem.style.animationDelay = `${index * 0.1}s`;
            
            const stringText = document.createElement('span');
            stringText.className = 'string-text';
            stringText.textContent = string;
            
            const copyBtn = document.createElement('button');
            copyBtn.className = 'copy-btn';
            copyBtn.textContent = 'Copy';
            copyBtn.onclick = () => copyToClipboard(string, copyBtn);
            
            stringItem.appendChild(stringText);
            stringItem.appendChild(copyBtn);
            stringsList.appendChild(stringItem);
        });
    }

    function copyToClipboard(text, button) {
        navigator.clipboard.writeText(text).then(() => {
            button.textContent = 'Copied!';
            button.classList.add('copied');
            
            setTimeout(() => {
                button.textContent = 'Copy';
                button.classList.remove('copied');
            }, 2000);
        }).catch(err => {
            console.error('Failed to copy:', err);
            showError('Failed to copy to clipboard');
        });
    }

    function showError(message) {
        errorDiv.textContent = message;
        errorDiv.classList.remove('hidden');
    }

    async function checkHealth() {
        try {
            const response = await fetch('/health');
            const data = await response.json();
            
            if (data.status === 'healthy') {
                const maxAllowed = Math.min(data.available_snapshots, 100);
                statusSpan.textContent = `System healthy • ${data.available_snapshots} snapshots available • max ${maxAllowed} strings`;
                statusSpan.className = 'status healthy';
                
                // Update max string count based on available snapshots
                updateMaxStringCount(data.available_snapshots);
            } else {
                statusSpan.textContent = 'System unhealthy';
                statusSpan.className = 'status unhealthy';
            }
        } catch (error) {
            statusSpan.textContent = 'Cannot connect to server';
            statusSpan.className = 'status unhealthy';
        }
    }

    function updateMaxStringCount(availableSnapshots) {
        const maxCount = Math.min(availableSnapshots, 100); // Still respect the original 100 limit
        
        // Update slider max
        countSlider.max = maxCount;
        
        // Update input max
        countInput.max = maxCount;
        
        // If current value exceeds new max, adjust it
        if (parseInt(countSlider.value) > maxCount) {
            countSlider.value = maxCount;
            countInput.value = maxCount;
            countDisplay.textContent = maxCount;
            // Save the adjusted value
            localStorage.setItem('stringCount', maxCount);
        }
    }

    function loadSettings() {
        // Load active tab
        const activeTab = localStorage.getItem('activeTab') || 'strings';
        
        // Set active tab
        tabButtons.forEach(btn => {
            btn.classList.remove('active');
            if (btn.getAttribute('data-tab') === activeTab) {
                btn.classList.add('active');
            }
        });
        
        tabContents.forEach(content => {
            content.classList.remove('active');
            if (content.getAttribute('data-tab') === activeTab) {
                content.classList.add('active');
            }
        });

        // Load string generation settings
        const stringLength = localStorage.getItem('stringLength');
        if (stringLength) {
            lengthSlider.value = stringLength;
            lengthInput.value = stringLength;
        }

        const stringCount = localStorage.getItem('stringCount');
        if (stringCount) {
            countSlider.value = stringCount;
            countInput.value = stringCount;
            countDisplay.textContent = stringCount;
        }

        // Load character type settings
        const charTypes = JSON.parse(localStorage.getItem('charTypes') || '["uppercase", "lowercase", "numbers"]');
        document.querySelectorAll('input[name="charType"]').forEach(checkbox => {
            checkbox.checked = charTypes.includes(checkbox.value);
        });

        // Load passphrase settings
        const wordCount = localStorage.getItem('wordCount');
        if (wordCount) {
            wordCountSlider.value = wordCount;
            wordCountInput.value = wordCount;
            wordCountDisplay.textContent = wordCount;
        }

        const capitalizeWords = localStorage.getItem('capitalizeWords');
        if (capitalizeWords !== null) {
            document.getElementById('capitalizeWords').checked = capitalizeWords === 'true';
        }

        const separateWithDashes = localStorage.getItem('separateWithDashes');
        if (separateWithDashes !== null) {
            document.getElementById('separateWithDashes').checked = separateWithDashes === 'true';
        }

        const addDigit = localStorage.getItem('addDigit');
        if (addDigit !== null) {
            document.getElementById('addDigit').checked = addDigit === 'true';
        }
    }

    function setupSettingsSync() {
        // Save active tab when clicking tab buttons
        tabButtons.forEach(button => {
            button.addEventListener('click', function() {
                localStorage.setItem('activeTab', this.getAttribute('data-tab'));
            });
        });

        // Save string generation settings
        lengthSlider.addEventListener('input', function() {
            localStorage.setItem('stringLength', this.value);
        });

        lengthInput.addEventListener('input', function() {
            localStorage.setItem('stringLength', this.value);
        });

        countSlider.addEventListener('input', function() {
            localStorage.setItem('stringCount', this.value);
        });

        countInput.addEventListener('input', function() {
            localStorage.setItem('stringCount', this.value);
        });

        // Save character type settings
        document.querySelectorAll('input[name="charType"]').forEach(checkbox => {
            checkbox.addEventListener('change', function() {
                const charTypes = Array.from(document.querySelectorAll('input[name="charType"]:checked'))
                    .map(cb => cb.value);
                localStorage.setItem('charTypes', JSON.stringify(charTypes));
            });
        });

        // Save passphrase settings
        wordCountSlider.addEventListener('input', function() {
            localStorage.setItem('wordCount', this.value);
        });

        wordCountInput.addEventListener('input', function() {
            localStorage.setItem('wordCount', this.value);
        });

        document.getElementById('capitalizeWords').addEventListener('change', function() {
            localStorage.setItem('capitalizeWords', this.checked);
        });

        document.getElementById('separateWithDashes').addEventListener('change', function() {
            localStorage.setItem('separateWithDashes', this.checked);
        });

        document.getElementById('addDigit').addEventListener('change', function() {
            localStorage.setItem('addDigit', this.checked);
        });
    }
});