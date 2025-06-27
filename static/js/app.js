document.addEventListener('DOMContentLoaded', function() {
    const form = document.getElementById('generatorForm');
    const lengthSlider = document.getElementById('lengthSlider');
    const lengthInput = document.getElementById('lengthInput');
    const resultsDiv = document.getElementById('results');
    const stringsList = document.getElementById('stringsList');
    const errorDiv = document.getElementById('error');
    const statusSpan = document.getElementById('status');

    // Sync slider and input
    lengthSlider.addEventListener('input', function() {
        lengthInput.value = this.value;
    });

    lengthInput.addEventListener('input', function() {
        lengthSlider.value = this.value;
    });

    // Check system health
    checkHealth();
    setInterval(checkHealth, 30000); // Check every 30 seconds

    // Form submission
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
            displayResults(data.strings);
            
        } catch (error) {
            showError(error.message);
        } finally {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Generate Random Strings';
        }
    });

    function displayResults(strings) {
        resultsDiv.classList.remove('hidden');
        
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
                statusSpan.textContent = `System healthy • ${data.available_snapshots} snapshots available`;
                statusSpan.className = 'status healthy';
            } else {
                statusSpan.textContent = 'System unhealthy';
                statusSpan.className = 'status unhealthy';
            }
        } catch (error) {
            statusSpan.textContent = 'Cannot connect to server';
            statusSpan.className = 'status unhealthy';
        }
    }
});