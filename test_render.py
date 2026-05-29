import logging
from videoforge.skills.video_render.hyperframes_provider import HyperFramesProvider

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    print("Starting Phase 1 Render Test...")
    
    # 1. Initialize the provider
    config = {
        "hyperframes_version": "0.6.55"
    }
    provider = HyperFramesProvider(config)
    
    # 2. Prepare mock data
    # In a real scenario, this would come from the PipelineState
    mock_data = {
        "title": "VideoForge",
        "subtitle": "Phase 1 Render Test"
    }
    
    # 3. Call render
    print("Calling provider.render()...")
    result = provider.render(
        template="main_template",
        data=mock_data
    )
    
    print(f"Render completed successfully!")
    print(f"Output video path: {result.video_path}")
    print(f"Resolution: {result.resolution}")

if __name__ == "__main__":
    main()
