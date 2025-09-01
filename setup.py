#!/usr/bin/env python3
"""
Video Chapter Automater - Interactive Setup Script

This script provides a user-friendly installation and setup experience
for the Video Chapter Automater project, featuring:

- Interactive setup wizard with Rich TUI
- System requirements validation
- GPU detection and configuration
- Dependency management with uv
- User preference configuration
"""

import sys
import subprocess
from pathlib import Path


def check_python_version():
    """Ensure minimum Python version is met."""
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        print(
            f"   Current version: {sys.version_info.major}.{sys.version_info.minor}")
        print("   Please upgrade Python and try again.")
        return False
    return True


def install_rich_if_needed():
    """Install Rich library if not available, needed for the setup wizard."""
    try:
        import rich
        return True
    except ImportError:
        print("📦 Installing Rich TUI library for setup wizard...")
        try:
            # Try uv first
            subprocess.run([
                "uv", "add", "rich"
            ], check=True, capture_output=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            try:
                # Fallback to pip
                subprocess.run([
                    sys.executable, "-m", "pip", "install", "rich"
                ], check=True, capture_output=True)
                return True
            except subprocess.CalledProcessError as e:
                print(f"❌ Failed to install Rich library: {e}")
                print("   Please install manually: pip install rich")
                return False


def main():
    """Main setup entry point."""
    print("🎬 Video Chapter Automater - Interactive Setup")
    print("=" * 50)

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Ensure Rich is available for the setup wizard
    if not install_rich_if_needed():
        sys.exit(1)

    # Import and run the setup wizard
    try:
        # Add src to path for local imports
        project_root = Path(__file__).parent
        src_path = project_root / "src"
        if src_path.exists():
            sys.path.insert(0, str(src_path))

        from video_chapter_automater.setup_wizard import SetupWizard

        # Run the interactive setup wizard
        wizard = SetupWizard()
        success = wizard.run()

        if success:
            print("\n✅ Setup completed successfully!")
            print("🚀 You can now use: video-chapter-automater your_video.mp4")
            sys.exit(0)
        else:
            print("\n❌ Setup was cancelled or failed.")
            sys.exit(1)

    except ImportError as e:
        print(f"❌ Failed to import setup wizard: {e}")
        print("   Please ensure the project structure is correct.")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\n\n⏹️  Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during setup: {e}")
        print("   Please check the installation and try again.")
        sys.exit(1)


if __name__ == "__main__":
    main()
