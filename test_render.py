import json
import logging
from videoforge.config import load_config
from videoforge.skills.video_render.hyperframes_provider import HyperFramesProvider

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def main():
    print("=== Testing Render Step Only ===")
    
    # 读取现有的 data.js
    with open("templates/hyperframes/main_template/data.js", "r", encoding="utf-8") as f:
        js_content = f.read()
        
    json_str = js_content.replace("window.__VIDEOFORGE_DATA__ = ", "").strip().rstrip(";")
    data = json.loads(json_str)
    
    print("Using assets from templates/hyperframes/main_template/assets/ as defined in data.js")

    config = load_config()
    renderer = HyperFramesProvider(config)
    
    # 重新触发渲染与混音
    result = renderer.render("main_template", data)
    print(f"=== Render Test Completed ===")
    print(f"Final output: {result.video_path}")

if __name__ == "__main__":
    main()
