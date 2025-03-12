// Progress page functionality
function initProgressTracking(debateId, roundsCount) {
    console.log(`Initializing progress tracking for debate ${debateId} with ${roundsCount} rounds`);
    
    const progressBar = document.getElementById('progress-bar');
    const statusMessage = document.getElementById('status-message');
    
    // Map of step IDs to their DOM elements
    const stepElements = {};
    
    // Initialize step elements map
    document.querySelectorAll('.step-item').forEach(element => {
        const id = element.id;
        stepElements[id] = element;
    });
    
    console.log('Step elements initialized:', Object.keys(stepElements));
    
    // Define the step order explicitly to ensure correct sequence
    const stepOrder = ['starting'];
    stepOrder.push('pro_initial');
    stepOrder.push('con_initial');
    
    // Add round steps in order
    for (let i = 2; i <= roundsCount; i++) {
        stepOrder.push(`pro_round_${i}`);
        stepOrder.push(`con_round_${i}`);
    }
    
    stepOrder.push('judging');
    stepOrder.push('completed');
    
    console.log('Step order defined:', stepOrder);
    
    // Map of status values to step IDs
    const stepsMap = {
        'starting': 'step-init',
        'pro_initial': 'step-pro-initial',
        'con_initial': 'step-con-initial',
        'judging': 'step-judging',
        'completed': 'step-completed'
    };
    
    // Add round steps to the map
    for (let i = 2; i <= roundsCount; i++) {
        stepsMap[`pro_round_${i}`] = `step-pro-round-${i}`;
        stepsMap[`con_round_${i}`] = `step-con-round-${i}`;
    }
    
    console.log('Step map initialized:', stepsMap);
    
    // Keep track of the current step
    let currentStepId = null;
    let currentStepIndex = -1;
    
    // Track if we're using the fallback polling method
    let usingPollingFallback = false;
    let pollingInterval = null;
    let debugInfo = null;
    
    // Function to update the progress UI
    function updateProgress(data) {
        console.log('Received progress update:', data);
        
        // Update progress bar
        const progress = data.progress || 0;
        progressBar.style.width = `${progress}%`;
        progressBar.setAttribute('aria-valuenow', progress);
        progressBar.textContent = `${progress}%`;
        
        // Update status message
        if (data.message) {
            statusMessage.textContent = data.message;
        }
        
        // Get the step ID for the current status
        const currentStep = data.status;
        if (!currentStep) {
            console.warn('No status in update data');
            return;
        }
        
        const stepId = stepsMap[currentStep];
        console.log('Current step:', currentStep, 'Step ID:', stepId);
        
        if (!stepId) {
            console.warn(`Unknown step status: ${currentStep}`);
            return;
        }
        
        // Find the index of the current step in the order
        const stepIndex = stepOrder.indexOf(currentStep);
        if (stepIndex === -1) {
            console.warn(`Step ${currentStep} not found in step order`);
            return;
        }
        
        // Only proceed if this step is the next in sequence or later
        if (stepIndex < currentStepIndex) {
            console.warn(`Received out-of-order step update: ${currentStep} (index ${stepIndex}) is before current step index ${currentStepIndex}`);
            return;
        }
        
        console.log(`Processing step ${currentStep} (index ${stepIndex}), current index is ${currentStepIndex}`);
        
        // Update all steps based on their position in the sequence
        for (let i = 0; i < stepOrder.length; i++) {
            const status = stepOrder[i];
            const id = stepsMap[status];
            const element = stepElements[id];
            
            if (!element) {
                console.warn(`Step element not found: ${id}`);
                continue;
            }
            
            if (i === stepIndex) {
                // Current active step
                console.log(`Marking step ${id} as active`);
                element.className = 'step-item step-active';
                element.querySelector('.step-icon').textContent = '🔄';
            } else if (i < stepIndex) {
                // Previous completed steps
                console.log(`Marking step ${id} as completed`);
                element.className = 'step-item step-completed';
                element.querySelector('.step-icon').textContent = '✅';
            } else {
                // Future pending steps
                console.log(`Marking step ${id} as pending`);
                element.className = 'step-item step-pending';
                element.querySelector('.step-icon').textContent = '⏳';
            }
        }
        
        // Update current step tracking
        currentStepId = stepId;
        currentStepIndex = stepIndex;
        
        // If debate is completed, redirect to results page
        if (data.completed && !data.error) {
            console.log('Debate completed, redirecting to results page');
            const baseUrl = window.location.origin;
            window.location.href = `${baseUrl}/debate/${debateId}/results`;
        }
        
        // If there was an error, show it
        if (data.error) {
            console.error('Error in debate:', data.error);
            statusMessage.textContent = `Error: ${data.error}`;
            statusMessage.style.color = 'red';
            progressBar.className = 'progress-bar bg-danger';
        }
        
        // Update last activity time
        lastActivityTime = Date.now();
    }
    
    // Function to create and set up the EventSource
    function setupEventSource() {
        // Get the base URL from the current location
        const baseUrl = window.location.origin;
        const progressUrl = `${baseUrl}/debate/${debateId}/progress`;
        
        console.log(`Setting up EventSource for ${progressUrl}`);
        const eventSource = new EventSource(progressUrl);
        
        eventSource.onopen = function() {
            console.log('EventSource connection opened');
            // Add debug info to the page
            addDebugInfo('SSE connection opened');
        };
        
        eventSource.onmessage = function(event) {
            console.log('Received event data:', event.data);
            try {
                const data = JSON.parse(event.data);
                updateProgress(data);
                
                // Close the connection if the debate is completed or errored
                if (data.completed || data.error) {
                    console.log('Closing EventSource connection');
                    eventSource.close();
                }
            } catch (error) {
                console.error('Error parsing event data:', error, event.data);
                addDebugInfo(`Error parsing event data: ${error.message}`);
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('EventSource error:', error);
            addDebugInfo(`EventSource error: ${error}`);
            eventSource.close();
            
            // If we're not already using the polling fallback, switch to it
            if (!usingPollingFallback) {
                console.log('Switching to polling fallback method');
                addDebugInfo('Switching to polling fallback method');
                usingPollingFallback = true;
                setupPollingFallback();
            } else {
            // Try to reconnect after a delay
            console.log('Attempting to reconnect in 3 seconds...');
                addDebugInfo('Attempting to reconnect SSE in 3 seconds...');
            setTimeout(() => {
                const newEventSource = setupEventSource();
                return newEventSource;
            }, 3000);
            }
        };
        
        return eventSource;
    }
    
    // Function to set up polling fallback
    function setupPollingFallback() {
        console.log('Setting up polling fallback');
        addDebugInfo('Setting up polling fallback');
        
        // Clear any existing polling interval
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
        
        // Function to poll for updates
        async function pollForUpdates() {
            try {
                const baseUrl = window.location.origin;
                const jsonUrl = `${baseUrl}/debate/${debateId}/progress/json`;
                console.log(`Polling ${jsonUrl} for updates`);
                
                const response = await fetch(jsonUrl, {
                    headers: {
                        'Cache-Control': 'no-cache',
                        'Pragma': 'no-cache'
                    },
                    credentials: 'include'
                });
                
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                
                const data = await response.json();
                console.log('Received polling data:', data);
                updateProgress(data);
                
                // If debate is completed or errored, stop polling
                if (data.completed || data.error) {
                    console.log('Debate completed or errored, stopping polling');
                    addDebugInfo('Debate completed or errored, stopping polling');
                    clearInterval(pollingInterval);
                }
            } catch (error) {
                console.error('Error polling for updates:', error);
                addDebugInfo(`Error polling for updates: ${error.message}`);
                
                // If we get too many consecutive errors, try to fetch debug info
                fetchDebugInfo();
            }
        }
        
        // Poll immediately
        pollForUpdates();
        
        // Then set up interval (every 2 seconds)
        pollingInterval = setInterval(pollForUpdates, 2000);
    }
    
    // Function to fetch debug information
    async function fetchDebugInfo() {
        try {
            const baseUrl = window.location.origin;
            const debugUrl = `${baseUrl}/debug/connection`;
            console.log(`Fetching debug info from ${debugUrl}`);
            
            const response = await fetch(debugUrl, {
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                },
                credentials: 'include'
            });
            
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            console.log('Debug info:', data);
            debugInfo = data;
            
            // Add debug info to the page
            addDebugInfo(`Debug info: Client IP: ${data.client_ip}, Railway Env: ${data.railway_env}`);
            
            // Create a hidden debug element with all the info
            const debugElement = document.createElement('div');
            debugElement.id = 'debug-data';
            debugElement.style.display = 'none';
            debugElement.textContent = JSON.stringify(data, null, 2);
            document.body.appendChild(debugElement);
            
        } catch (error) {
            console.error('Error fetching debug info:', error);
        }
    }
    
    // Function to add debug info to the page
    function addDebugInfo(message) {
        // Check if debug container exists, if not create it
        let debugContainer = document.getElementById('debug-container');
        if (!debugContainer) {
            debugContainer = document.createElement('div');
            debugContainer.id = 'debug-container';
            debugContainer.className = 'mt-4 p-3 border rounded bg-light';
            debugContainer.innerHTML = '<h5>Debug Information</h5><div id="debug-messages"></div>';
            
            // Add a button to show/hide debug info
            const toggleButton = document.createElement('button');
            toggleButton.className = 'btn btn-sm btn-secondary mt-2';
            toggleButton.textContent = 'Show/Hide Debug Info';
            toggleButton.onclick = function() {
                const messagesDiv = document.getElementById('debug-messages');
                messagesDiv.style.display = messagesDiv.style.display === 'none' ? 'block' : 'none';
            };
            
            debugContainer.appendChild(toggleButton);
            
            // Add it after the steps container
            const stepsContainer = document.querySelector('.steps-container');
            stepsContainer.parentNode.insertBefore(debugContainer, stepsContainer.nextSibling);
            
            // Initially hide the messages
            document.getElementById('debug-messages').style.display = 'none';
        }
        
        // Add the message
        const messagesDiv = document.getElementById('debug-messages');
        const messageElement = document.createElement('div');
        messageElement.className = 'debug-message';
        messageElement.innerHTML = `<small>[${new Date().toISOString()}] ${message}</small>`;
        messagesDiv.appendChild(messageElement);
    }
    
    // Detect if we're in a production environment
    const isProduction = window.location.hostname !== 'localhost' && 
                         window.location.hostname !== '127.0.0.1';
    
    // Initial setup - use polling in production, try EventSource in development
    let eventSource = null;
    
    // Always fetch debug info at startup
    fetchDebugInfo();
    
    if (isProduction) {
        console.log('Production environment detected, using polling method');
        addDebugInfo('Production environment detected, using polling method');
        usingPollingFallback = true;
        setupPollingFallback();
    } else if (typeof EventSource !== 'undefined') {
        console.log('Development environment, EventSource is supported, using SSE');
        addDebugInfo('Development environment, EventSource is supported, using SSE');
        eventSource = setupEventSource();
    } else {
        console.log('EventSource is not supported, using polling fallback');
        addDebugInfo('EventSource is not supported, using polling fallback');
        usingPollingFallback = true;
        setupPollingFallback();
    }
    
    // Set up a check to verify the connection is still active
    let lastActivityTime = Date.now();
    
    // Function to check if connection is still active
    function checkConnection() {
        const inactiveTime = Date.now() - lastActivityTime;
        
        // If no activity for more than 30 seconds, try to reconnect
        if (inactiveTime > 30000) {
            console.warn('No activity detected for 30 seconds, reconnecting...');
            addDebugInfo('No activity detected for 30 seconds, reconnecting...');
            
            if (usingPollingFallback) {
                // If using polling, restart it
                setupPollingFallback();
            } else if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
                // If using SSE, close and reopen
                eventSource.close();
                eventSource = setupEventSource();
            }
            
            lastActivityTime = Date.now();
        }
    }
    
    // Check connection every 10 seconds
    const connectionCheckInterval = setInterval(checkConnection, 10000);
    
    // Clean up when leaving the page
    window.addEventListener('beforeunload', function() {
        if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
            eventSource.close();
        }
        if (pollingInterval) {
            clearInterval(pollingInterval);
        }
        clearInterval(connectionCheckInterval);
    });
} 