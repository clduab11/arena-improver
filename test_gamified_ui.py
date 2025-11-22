"""Quick test script for the gamified UI components."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import extract_palette_from_image, VILLAIN_CSS

def test_color_extraction():
    """Test the color extraction function with None input."""
    print("Testing color extraction with None...")
    colors = extract_palette_from_image(None)
    print(f"Default colors: {colors}")
    assert len(colors) == 3
    assert all(c.startswith('#') for c in colors)
    print("✓ Color extraction test passed!")

def test_css_loaded():
    """Test that the CSS is loaded."""
    print("Testing CSS loading...")
    assert "villain-header" in VILLAIN_CSS
    assert "primary-action-btn" in VILLAIN_CSS
    assert "glitch" in VILLAIN_CSS
    assert "button-glow" in VILLAIN_CSS
    print("✓ CSS loaded successfully!")

def test_imports():
    """Test that all required modules can be imported."""
    print("Testing imports...")
    from app import (
        create_gradio_interface,
        build_theme_designer_tab,
        GRADIO_BUILDERS
    )
    print(f"✓ Imports successful! Found {len(GRADIO_BUILDERS)} registered builders")

if __name__ == "__main__":
    print("=" * 60)
    print("Gamified UI Component Tests")
    print("=" * 60)

    try:
        test_color_extraction()
        test_css_loaded()
        test_imports()

        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
