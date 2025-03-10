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
            window.location.href = `/debate/${debateId}/results`;
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
        console.log(`Setting up EventSource for /debate/${debateId}/progress`);
        const eventSource = new EventSource(`/debate/${debateId}/progress`);
        
        eventSource.onopen = function() {
            console.log('EventSource connection opened');
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
            }
        };
        
        eventSource.onerror = function(error) {
            console.error('EventSource error:', error);
            eventSource.close();
            
            // Try to reconnect after a delay
            console.log('Attempting to reconnect in 3 seconds...');
            setTimeout(() => {
                const newEventSource = setupEventSource();
                return newEventSource;
            }, 3000);
        };
        
        return eventSource;
    }
    
    // Initial setup of EventSource
    let eventSource = setupEventSource();
    
    // Set up a check to verify the connection is still active
    let lastActivityTime = Date.now();
    
    // Function to check if connection is still active
    function checkConnection() {
        const inactiveTime = Date.now() - lastActivityTime;
        
        // If no activity for more than 30 seconds, try to reconnect
        if (inactiveTime > 30000) {
            console.warn('No activity detected for 30 seconds, reconnecting...');
            if (eventSource && eventSource.readyState !== EventSource.CLOSED) {
                eventSource.close();
            }
            eventSource = setupEventSource();
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
        clearInterval(connectionCheckInterval);
    });
} 