import pytest
import os
import json
from pathlib import Path
from repacku.core.folder_analyzer import FolderAnalyzer
from repacku.core.zip_compressor import ZipCompressor

def test_selective_compression_only_images(tmp_path):
    # Setup: Create a folder with one image and one video
    src_dir = tmp_path / "test_folder"
    src_dir.mkdir()
    (src_dir / "image1.jpg").write_text("dummy image")
    (src_dir / "image2.png").write_text("dummy image")
    (src_dir / "video1.mp4").write_text("dummy video")
    
    # Analyze with target_file_types=['image']
    analyzer = FolderAnalyzer()
    root_info = analyzer.analyze_folder_structure(src_dir, target_file_types=['image'], use_fast_scanner=True)
    
    # Check if video extension is in file_extensions
    # If the bug exists, .mp4 will be present
    print(f"File extensions in analysis: {root_info.file_extensions}")
    
    # Generate config JSON
    config_path = tmp_path / "config.json"
    analyzer.generate_config_json(src_dir, output_path=config_path, target_file_types=['image'], root_info=root_info)
    
    # Build tasks in ZipCompressor
    compressor = ZipCompressor()
    with open(config_path, 'r', encoding='utf-8') as f:
        config_data = json.load(f)
    
    folders_to_compress = [config_data["folder_tree"]]
    tasks = compressor._build_compression_tasks(folders_to_compress, str(tmp_path), ['image'])
    
    assert len(tasks) == 1
    task = tasks[0]
    
    # Verify that only .jpg is in file_extensions for the task
    assert ".jpg" in task.file_extensions
    assert ".mp4" not in task.file_extensions, f"Bug reproduced: .mp4 found in selective compression tasks for image-only mode. Task extensions: {task.file_extensions}"

if __name__ == "__main__":
    pytest.main([__file__])
