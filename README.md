# Description:  
    A GUI image preprocessing tool designed for embedded graphics frameworks
    (e.g., STM32C0 TouchGFX). It heavily optimizes standard RGB images into strictly
    compressed 8-bit palette (L8 format) images.

    By employing a proprietary Pre-quantization High-Frequency Noise Injection
    algorithm combined with "Floyd-Steinberg Error Diffusion", it mathematically
    eliminates color banding (step artifacts) in smooth gradients. This allows for
    photorealistic UI assets using minimal RAM/Flash footprints (e.g., pseudo true-color
    gradients using only a 64-color palette).

# Key Features:  
    1. Custom Palette Downsampling: Dynamic control from 2 to 256 colors.
    2. Noise-Driven Dithering: Adjustable noise matrix injection to break color steps.
    3. Non-blocking UI Pipeline: Async multi-threading and debouncing implementation.
    4. Ready-to-Use Export: Outputs compliant 8-bit P-mode PNGs.

# Dependencies:  
    Python 3.13  
    Pillow 12.2.0  
    numpy 2.4.5  
