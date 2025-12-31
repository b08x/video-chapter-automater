"""
Python-native chapter format conversion.

Converts PySceneDetect CSV output to FFmpeg-compatible chapter format.
"""

from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ChapterEntry:
    """Represents a single chapter with start time and optional metadata."""
    
    def __init__(self, start_ms: int, end_ms: Optional[int] = None, title: Optional[str] = None):
        self.start_ms = start_ms
        self.end_ms = end_ms
        self.title = title or f"Chapter {self.start_ms}"
    
    def to_ffmpeg_format(self) -> str:
        """Convert chapter to FFmpeg metadata format."""
        lines = [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={self.start_ms}"
        ]
        
        if self.end_ms is not None:
            lines.append(f"END={self.end_ms}")
        
        if self.title:
            # Escape title for FFmpeg metadata
            escaped_title = self.title.replace('=', '\\=').replace('\n', ' ').replace('\r', '')
            lines.append(f"title={escaped_title}")
        
        return '\n'.join(lines)


class ChapterConverter:
    """Converts scene detection results to video chapter formats."""
    
    @staticmethod
    def parse_pyscenedetect_csv(csv_path: Path) -> List[ChapterEntry]:
        """
        Parse PySceneDetect CSV output into chapter entries.
        
        Expected CSV format:
        Scene Number,Start Frame,Start Timecode,Start Time (seconds),End Frame,End Timecode,End Time (seconds),Length (frames),Length (timecode),Length (seconds)
        1,1,00:00:00.000,0.0,750,00:00:25.000,25.0,749,00:00:24.958,24.958
        """
        chapters = []
        
        try:
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                
                for i, row in enumerate(reader):
                    try:
                        # Get start time in seconds and convert to milliseconds
                        start_seconds = float(row.get('Start Time (seconds)', 0))
                        start_ms = int(start_seconds * 1000)
                        
                        # Get end time if available
                        end_seconds = row.get('End Time (seconds)')
                        end_ms = int(float(end_seconds) * 1000) if end_seconds else None
                        
                        # Generate chapter title
                        scene_number = row.get('Scene Number', str(i + 1))
                        title = f"Chapter {scene_number}"
                        
                        chapter = ChapterEntry(start_ms, end_ms, title)
                        chapters.append(chapter)
                        
                    except (ValueError, KeyError) as e:
                        logger.warning(f"Skipping invalid CSV row {i + 1}: {e}")
                        continue
                        
        except (FileNotFoundError, IOError) as e:
            raise FileNotFoundError(f"Could not read PySceneDetect CSV file: {csv_path}") from e
        except Exception as e:
            raise ValueError(f"Error parsing PySceneDetect CSV: {e}") from e
        
        if not chapters:
            raise ValueError("No valid chapters found in PySceneDetect CSV")
        
        logger.info(f"Parsed {len(chapters)} chapters from {csv_path}")
        return chapters
    
    @staticmethod
    def chapters_to_ffmpeg(chapters: List[ChapterEntry]) -> str:
        """Convert chapter entries to FFmpeg metadata format."""
        if not chapters:
            return ""
        
        # Add metadata header
        lines = [
            ";FFMETADATA1",
            ""
        ]
        
        # Add each chapter
        for chapter in chapters:
            lines.append(chapter.to_ffmpeg_format())
            lines.append("")  # Empty line between chapters
        
        return '\n'.join(lines)
    
    @classmethod
    def pyscenedetect_to_ffmpeg(cls, csv_path: Path) -> str:
        """
        Convert PySceneDetect CSV directly to FFmpeg chapter format.
        
        This is the main conversion function that replaces chapconv.
        """
        chapters = cls.parse_pyscenedetect_csv(csv_path)
        return cls.chapters_to_ffmpeg(chapters)
    
    @staticmethod
    def validate_ffmpeg_chapters(chapters_text: str) -> bool:
        """Validate that the generated chapters are in correct FFmpeg format."""
        if not chapters_text.strip():
            return False
        
        lines = chapters_text.strip().split('\n')
        
        # Check for metadata header
        if not lines[0].startswith(';FFMETADATA'):
            return False
        
        # Look for at least one chapter
        has_chapter = any(line.strip() == '[CHAPTER]' for line in lines)
        if not has_chapter:
            return False
        
        # Basic validation of chapter structure
        in_chapter = False
        for line in lines:
            line = line.strip()
            if line == '[CHAPTER]':
                in_chapter = True
            elif in_chapter and line.startswith('START='):
                try:
                    int(line.split('=', 1)[1])
                except (ValueError, IndexError):
                    return False
        
        return True


def convert_pyscenedetect_csv(csv_path: Path, output_path: Optional[Path] = None) -> str:
    """
    Convenience function to convert PySceneDetect CSV to FFmpeg chapters.
    
    Args:
        csv_path: Path to PySceneDetect CSV file
        output_path: Optional path to write chapters file (if None, returns string)
        
    Returns:
        FFmpeg chapter format string
    """
    converter = ChapterConverter()
    chapters_text = converter.pyscenedetect_to_ffmpeg(csv_path)
    
    if not converter.validate_ffmpeg_chapters(chapters_text):
        raise ValueError("Generated chapters failed validation")
    
    if output_path:
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(chapters_text)
        logger.info(f"Chapters written to {output_path}")
    
    return chapters_text


# Backward compatibility with chapconv-style usage
def chapconv_convert(input_file: Path, input_format: str = "pyscenedetect", 
                    output_format: str = "ffmetadata") -> str:
    """
    Backward-compatible function that mimics chapconv behavior.
    
    This allows existing code to work without modification.
    """
    if input_format.lower() != "pyscenedetect":
        raise ValueError(f"Unsupported input format: {input_format}")
    
    if output_format.lower() != "ffmetadata":
        raise ValueError(f"Unsupported output format: {output_format}")
    
    return convert_pyscenedetect_csv(input_file)
