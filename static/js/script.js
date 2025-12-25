// Global variables for weight estimation
let currentWeightFile = null;
let isVideo = false;

// Navigation Toggle
const hamburger = document.querySelector('.hamburger');
const navMenu = document.querySelector('.nav-menu');

if (hamburger) {
    hamburger.addEventListener('click', () => {
        hamburger.classList.toggle('active');
        navMenu.classList.toggle('active');
    });
}

// Close mobile menu when clicking on a link
document.querySelectorAll('.nav-link').forEach(n => n.addEventListener('click', () => {
    hamburger.classList.remove('active');
    navMenu.classList.remove('active');
}));

// File Upload Handling
document.addEventListener('DOMContentLoaded', function() {
    // Dashboard uploads
    const photoUpload = document.getElementById('photo-upload');
    const videoUpload = document.getElementById('video-upload');
    const photoOption = document.querySelector('.upload-option:nth-child(1)');
    const videoOption = document.querySelector('.upload-option:nth-child(2)');
    const analyzeBtn = document.getElementById('analyze-btn');

    if (photoOption && photoUpload) {
        photoOption.addEventListener('click', () => {
            photoUpload.click();
        });
    }

    if (videoOption && videoUpload) {
        videoOption.addEventListener('click', () => {
            videoUpload.click();
        });
    }

    // Disease detection uploads
    const broilerUpload = document.getElementById('broiler-upload');
    const broilerFile = document.getElementById('broiler-file');
    const fecalUpload = document.getElementById('fecal-upload');
    const fecalFile = document.getElementById('fecal-file');
    const analyzeBroiler = document.getElementById('analyze-broiler');
    const analyzeFecal = document.getElementById('analyze-fecal');

    if (broilerUpload && broilerFile) {
        broilerUpload.addEventListener('click', () => {
            broilerFile.click();
        });
    }

    if (fecalUpload && fecalFile) {
        fecalUpload.addEventListener('click', () => {
            fecalFile.click();
        });
    }

    // Weight estimation upload elements
    const weightFile = document.getElementById('weight-file');
    const weightVideoFile = document.getElementById('weight-video-file');
    const estimateWeight = document.getElementById('estimate-weight');
    const weightSelectedFile = document.getElementById('weight-selected-file');
    const mediaPreview = document.getElementById('media-preview');
    const loadingText = document.getElementById('loading-text');
    
    // Function to handle image upload option click
    function handleImageOptionClick() {
        console.log('Image option clicked');
        if (weightFile) {
            console.log('Triggering file input click');
            weightFile.click();
        } else {
            console.error('Weight file input not found');
        }
    }

    // Function to handle video upload option click
    function handleVideoOptionClick() {
        console.log('Video option clicked');
        if (weightVideoFile) {
            console.log('Triggering video input click');
            weightVideoFile.click();
        } else {
            console.error('Weight video file input not found');
        }
    }

    // Handle image upload option click
    const imageOption = document.getElementById('image-option');
    if (imageOption) {
        console.log('Image option element found');
        imageOption.addEventListener('click', handleImageOptionClick);
    } else {
        console.error('Image option element not found');
    }

    // Handle video upload option click
    const weightVideoOption = document.getElementById('video-option');
    if (weightVideoOption) {
        console.log('Video option element found');
        weightVideoOption.addEventListener('click', handleVideoOptionClick);
    } else {
        console.error('Video option element not found');
    }

    // Handle image file selection
    if (weightFile) {
        weightFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                // Reset video state
                if (weightVideoFile) weightVideoFile.value = '';
                isVideo = false;
                currentWeightFile = file;
                
                // Update UI
                if (weightSelectedFile) {
                    weightSelectedFile.innerHTML = `<span>Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</span>`;
                }
                
                // Show image preview
                mediaPreview.innerHTML = '';
                const img = document.createElement('img');
                img.src = URL.createObjectURL(file);
                img.style.maxWidth = '100%';
                img.style.maxHeight = '300px';
                img.style.borderRadius = '8px';
                mediaPreview.appendChild(img);
                
                // Enable estimate button
                if (estimateWeight) {
                    estimateWeight.disabled = false;
                }
            }
        });
    }

    // Handle video file selection
    if (weightVideoFile) {
        weightVideoFile.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (file) {
                // Reset image state
                if (weightFile) weightFile.value = '';
                isVideo = true;
                currentWeightFile = file;
                
                // Update UI
                if (weightSelectedFile) {
                    weightSelectedFile.innerHTML = `<span>Selected: ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} MB)</span>`;
                }
                
                // Show video preview
                mediaPreview.innerHTML = '';
                const video = document.createElement('video');
                video.src = URL.createObjectURL(file);
                video.controls = true;
                video.style.maxWidth = '100%';
                video.style.maxHeight = '300px';
                video.style.borderRadius = '8px';
                mediaPreview.appendChild(video);
                
                // Enable estimate button
                if (estimateWeight) {
                    estimateWeight.disabled = false;
                }
            }
        });
    }

    // Mock analysis functions
    if (analyzeBtn) {
        analyzeBtn.addEventListener('click', simulateDashboardAnalysis);
    }

    if (analyzeBroiler) {
        analyzeBroiler.addEventListener('click', simulateBroilerAnalysis);
    }

    if (analyzeFecal) {
        analyzeFecal.addEventListener('click', simulateFecalAnalysis);
    }

    if (estimateWeight) {
        estimateWeight.addEventListener('click', estimateWeightFromImage);
    }
});

// Mock analysis functions
function simulateDashboardAnalysis() {
    // Update result cards with mock data
    const resultValues = document.querySelectorAll('.result-value');
    if (resultValues.length >= 4) {
        resultValues[0].textContent = '24';
        resultValues[1].textContent = 'Healthy';
        resultValues[1].style.color = '#4CAF50';
        resultValues[2].textContent = '22';
        resultValues[3].textContent = '2';
        
        // Show success message
        alert('Analysis complete! 24 chickens detected, 22 healthy and 2 requiring attention.');
    }
}

function simulateBroilerAnalysis() {
    const scoreFill = document.querySelector('.score-fill');
    const scoreText = document.querySelector('.score-text');
    const diagnosisPlaceholder = document.querySelector('.diagnosis-placeholder');
    
    if (scoreFill && scoreText && diagnosisPlaceholder) {
        // Update confidence score
        const confidence = 87;
        scoreFill.style.width = `${confidence}%`;
        scoreText.textContent = `Confidence: ${confidence}%`;
        
        // Update diagnosis
        diagnosisPlaceholder.innerHTML = `
            <h4>Newcastle Disease Detected</h4>
            <p>Moderate severity with respiratory symptoms</p>
        `;
        
        // Update recommendations
        const recommendationsList = document.querySelector('.recommendations-list');
        if (recommendationsList) {
            recommendationsList.innerHTML = `
                <li>Isolate affected birds immediately</li>
                <li>Administer prescribed antibiotics</li>
                <li>Increase ventilation in the coop</li>
                <li>Consult with a veterinarian for vaccination options</li>
            `;
        }
        
        alert('Broiler analysis complete! Newcastle Disease detected with 87% confidence.');
    }
}

function simulateFecalAnalysis() {
    const scoreFill = document.querySelector('.score-fill');
    const scoreText = document.querySelector('.score-text');
    const diagnosisPlaceholder = document.querySelector('.diagnosis-placeholder');
    
    if (scoreFill && scoreText && diagnosisPlaceholder) {
        // Update confidence score
        const confidence = 92;
        scoreFill.style.width = `${confidence}%`;
        scoreText.textContent = `Confidence: ${confidence}%`;
        
        // Update diagnosis
        diagnosisPlaceholder.innerHTML = `
            <h4>Coccidiosis Detected</h4>
            <p>Intestinal parasite infection requiring treatment</p>
        `;
        
        // Update recommendations
        const recommendationsList = document.querySelector('.recommendations-list');
        if (recommendationsList) {
            recommendationsList.innerHTML = `
                <li>Administer anticoccidial medication</li>
                <li>Clean and disinfect housing area thoroughly</li>
                <li>Provide electrolyte solutions in drinking water</li>
                <li>Monitor for blood in droppings</li>
            `;
        }
        
        alert('Fecal analysis complete! Coccidiosis detected with 92% confidence.');
    }
}

async function estimateWeightFromImage() {
    if (!currentWeightFile) {
        alert('Please select an image or video first');
        return;
    }

    const estimateWeightBtn = document.getElementById('estimate-weight');
    const loadingSpinner = document.getElementById('weight-loading');
    const loadingText = document.getElementById('loading-text');
    const resultsSection = document.getElementById('weight-results-section');
    const weightValue = document.getElementById('weight-value');
    const weightDetectedCount = document.getElementById('weight-detected-count');
    const progressFill = document.getElementById('weight-progress-fill');
    const categoryValue = document.getElementById('weight-category-value');
    const annotatedImage = document.getElementById('weight-annotated-image');
    const broilerDetails = document.getElementById('broiler-details');
    const broilerList = document.getElementById('broiler-list');

    // Show loading spinner with appropriate message
    if (loadingSpinner) {
        loadingSpinner.style.display = 'flex';
        if (loadingText) {
            loadingText.textContent = isVideo 
                ? 'Processing video and estimating weights... This may take a moment...' 
                : 'Analyzing image and estimating weights...';
        }
    }
    
    if (estimateWeightBtn) estimateWeightBtn.disabled = true;
    if (resultsSection) resultsSection.style.display = 'none';

    const formData = new FormData();
    
    // Add the appropriate field name based on media type
    if (isVideo) {
        formData.append('video', currentWeightFile);
    } else {
        formData.append('image', currentWeightFile);
    }

    try {
        // Use the appropriate endpoint based on media type
        const endpoint = isVideo ? '/estimate-weight-video' : '/estimate-weight';
        
        const response = await fetch(endpoint, {
            method: 'POST',
            body: formData
        });

        const data = await response.json();

        if (!response.ok) {
            throw new Error(data.error || 'Failed to estimate weight');
        }

        if (data.success) {
            // Handle response based on media type
            if (isVideo) {
                // For video, we might have multiple frames or a summary
                if (data.results && data.results.length > 0) {
                    // Process video results (you can customize this based on your API response)
                    const avgWeight = data.average_weight || 0;
                    const totalDetected = data.total_detected || 0;
                    const weightCategory = data.weight_category || 'Unknown';
                    
                    // Convert kg to grams for display
                    const avgWeightGrams = Math.round(avgWeight * 1000);
                    
                    // Update UI with video results in grams
                    if (weightValue) weightValue.textContent = `${avgWeightGrams}g`;
                    if (weightDetectedCount) weightDetectedCount.textContent = `Detected ${totalDetected} broiler(s) in video`;
                    
                    // Update progress bar for video
                    if (progressFill) {
                        // Scale progress for grams (1500g-3500g range)
                        let progressPercentage = ((avgWeightGrams - 1500) / 2000) * 100;
                        progressPercentage = Math.max(0, Math.min(100, progressPercentage));
                        progressFill.style.width = `${progressPercentage}%`;
                    }
                    
                    // Update category
                    if (categoryValue) {
                        categoryValue.textContent = weightCategory;
                        if (weightCategory === 'Underweight') {
                            categoryValue.style.color = '#FF5722';
                        } else if (weightCategory === 'Optimal') {
                            categoryValue.style.color = '#4CAF50';
                        } else {
                            categoryValue.style.color = '#FF9800';
                        }
                    }
                    
                    // Show annotated image if available (could be a representative frame)
                    if (annotatedImage && data.representative_frame) {
                        annotatedImage.src = data.representative_frame;
                    }
                    
                    // Show broiler details if available
                    if (data.broilers && data.broilers.length > 0) {
                        if (broilerDetails) broilerDetails.style.display = 'block';
                        if (broilerList) {
                            broilerList.innerHTML = data.broilers.map((broiler, index) => `
                                <div class="broiler-item" style="padding: 1rem; margin: 0.5rem 0; background: #f5f5f5; border-radius: 8px;">
                                    <strong>Broiler #${index + 1}</strong>: ${Math.round(parseFloat(broiler.weight) * 1000)}g 
                                    ${broiler.confidence ? `(Confidence: ${(broiler.confidence * 100).toFixed(1)}%)` : ''}
                                    ${broiler.frame_time ? `<br><small>At ${broiler.frame_time}</small>` : ''}
                                </div>
                            `).join('');
                        }
                    } else {
                        if (broilerDetails) broilerDetails.style.display = 'none';
                    }
                }
            } else {
                // For images, use the existing logic
                if (annotatedImage && data.annotated_image) {
                    annotatedImage.src = data.annotated_image;
                }

                // Update weight value (use grams directly from backend)
                if (weightValue) {
                    weightValue.textContent = `${data.average_weight}g`;
                }

                // Update detected count
                if (weightDetectedCount) {
                    weightDetectedCount.textContent = `Detected ${data.detected_count} broiler(s)`;
                }

                // Show broiler details if available
                if (data.broilers && data.broilers.length > 0) {
                    if (broilerDetails) broilerDetails.style.display = 'block';
                    if (broilerList) {
                        broilerList.innerHTML = data.broilers.map((broiler, index) => `
                            <div class="broiler-item" style="padding: 1rem; margin: 0.5rem 0; background: #f5f5f5; border-radius: 8px;">
                                <strong>Broiler #${index + 1}</strong>: ${broiler.weight}g 
                                ${broiler.confidence ? `(Confidence: ${(parseFloat(broiler.confidence) * 100).toFixed(1)}%)` : ''}
                            </div>
                        `).join('');
                    }
                } else {
                    if (broilerDetails) broilerDetails.style.display = 'none';
                }
            }

            // Show results section
            if (resultsSection) {
                resultsSection.style.display = 'block';
                resultsSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
            }

            // Show success message
            const successMessage = isVideo
                ? `Video analysis complete! Processed ${data.processed_frames || 0} frames.`
                : `Weight estimation complete! Detected ${data.detected_count} broiler(s) with average weight of ${data.average_weight}g (${data.weight_category})`;
            
            alert(successMessage);
        } else {
            throw new Error(data.error || 'Unknown error occurred');
        }
    } catch (error) {
        console.error('Error estimating weight:', error);
        alert(`Error: ${error.message}`);
    } finally {
        // Hide loading spinner and re-enable button
        if (loadingSpinner) loadingSpinner.style.display = 'none';
        if (estimateWeightBtn) estimateWeightBtn.disabled = false;
    }
}