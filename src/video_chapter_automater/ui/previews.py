"""
Chapter preview and visualization components for VideoChapterAutomater.

Provides Rich-based UI widgets for displaying chapter information,
scene timings, and processing results.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.tree import Tree
from rich.text import Text

from ..preprocessing.scene_extractor import SceneInfo

console = Console()


@dataclass
class Chapter:
    """
    Represents a video chapter.

    Attributes:
        number: Chapter number (1-indexed)
        title: Chapter title
        start_time: Start time in seconds
        end_time: End time in seconds
        duration: Chapter duration in seconds
        image_paths: Paths to representative images
    """
    number: int
    title: str
    start_time: float
    end_time: float
    duration: float
    image_paths: List[Path] = None

    def __post_init__(self):
        """Initialize empty image paths list if none provided."""
        if self.image_paths is None:
            self.image_paths = []

    @staticmethod
    def format_time(seconds: float) -> str:
        """
        Format seconds as HH:MM:SS.

        Args:
            seconds: Time in seconds

        Returns:
            Formatted time string
        """
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    @classmethod
    def from_scene_info(cls, scene_info: SceneInfo, title: Optional[str] = None) -> Chapter:
        """
        Create Chapter from SceneInfo.

        Args:
            scene_info: Scene information
            title: Optional chapter title (default: "Chapter {number}")

        Returns:
            Chapter instance
        """
        if title is None:
            title = f"Chapter {scene_info.scene_number}"

        return cls(
            number=scene_info.scene_number,
            title=title,
            start_time=scene_info.start_time,
            end_time=scene_info.end_time,
            duration=scene_info.duration,
            image_paths=scene_info.image_paths
        )


class ChapterPreview:
    """
    Rich-based chapter preview and visualization.

    Provides formatted display of chapter information with timing,
    duration, and associated images.
    """

    def __init__(self, console: Optional[Console] = None):
        """
        Initialize chapter preview.

        Args:
            console: Rich Console instance (creates default if None)
        """
        self.console = console or Console()

    def create_table(
        self,
        chapters: List[Chapter],
        title: str = "Video Chapters"
    ) -> Table:
        """
        Create Rich Table with chapter information.

        Args:
            chapters: List of chapters to display
            title: Table title

        Returns:
            Formatted Rich Table
        """
        table = Table(title=title, show_header=True, header_style="bold cyan")

        # Add columns
        table.add_column("#", style="dim", width=4, justify="right")
        table.add_column("Title", style="cyan", no_wrap=False)
        table.add_column("Start", style="green", width=10, justify="right")
        table.add_column("End", style="green", width=10, justify="right")
        table.add_column("Duration", style="yellow", width=10, justify="right")
        table.add_column("Images", style="magenta", width=8, justify="right")

        # Add rows
        for chapter in chapters:
            table.add_row(
                str(chapter.number),
                chapter.title,
                Chapter.format_time(chapter.start_time),
                Chapter.format_time(chapter.end_time),
                f"{chapter.duration:.1f}s",
                str(len(chapter.image_paths))
            )

        return table

    def create_tree(
        self,
        chapters: List[Chapter],
        title: str = "📹 Video Chapters"
    ) -> Tree:
        """
        Create Rich Tree with hierarchical chapter information.

        Args:
            chapters: List of chapters to display
            title: Tree title

        Returns:
            Formatted Rich Tree
        """
        tree = Tree(f"[bold blue]{title}[/bold blue]")

        for chapter in chapters:
            # Create chapter node
            chapter_label = (
                f"[cyan]{chapter.title}[/cyan] "
                f"[dim]({Chapter.format_time(chapter.start_time)} - "
                f"{Chapter.format_time(chapter.end_time)})[/dim]"
            )
            chapter_node = tree.add(chapter_label)

            # Add duration info
            chapter_node.add(f"[yellow]Duration:[/yellow] {chapter.duration:.1f}s")

            # Add image info
            if chapter.image_paths:
                images_node = chapter_node.add(
                    f"[magenta]Images:[/magenta] {len(chapter.image_paths)}"
                )
                for img_path in chapter.image_paths[:3]:  # Show first 3
                    images_node.add(f"[dim]{img_path.name}[/dim]")
                if len(chapter.image_paths) > 3:
                    images_node.add(f"[dim]... and {len(chapter.image_paths) - 3} more[/dim]")

        return tree

    def create_panel(
        self,
        chapters: List[Chapter],
        title: str = "Chapter Preview"
    ) -> Panel:
        """
        Create Rich Panel with chapter table.

        Args:
            chapters: List of chapters to display
            title: Panel title

        Returns:
            Formatted Rich Panel containing chapter table
        """
        table = self.create_table(chapters, title="")
        return Panel(
            table,
            title=f"[bold blue]{title}[/bold blue]",
            border_style="blue"
        )

    def create_summary_panel(self, chapters: List[Chapter]) -> Panel:
        """
        Create summary panel with chapter statistics.

        Args:
            chapters: List of chapters

        Returns:
            Formatted Rich Panel with statistics
        """
        if not chapters:
            return Panel(
                "[yellow]No chapters detected[/yellow]",
                title="Summary",
                border_style="yellow"
            )

        # Calculate statistics
        total_duration = sum(c.duration for c in chapters)
        total_images = sum(len(c.image_paths) for c in chapters)
        avg_duration = total_duration / len(chapters) if chapters else 0
        avg_images = total_images / len(chapters) if chapters else 0

        # Create statistics table
        stats = Table.grid(padding=1)
        stats.add_column(style="cyan", no_wrap=True)
        stats.add_column(style="white")

        stats.add_row("Total Chapters:", f"{len(chapters)}")
        stats.add_row("Total Duration:", Chapter.format_time(total_duration))
        stats.add_row("Average Chapter:", f"{avg_duration:.1f}s")
        stats.add_row("Total Images:", f"{total_images}")
        stats.add_row("Images per Chapter:", f"{avg_images:.1f}")

        return Panel(
            stats,
            title="[bold green]Summary Statistics[/bold green]",
            border_style="green"
        )

    def display_chapters(
        self,
        chapters: List[Chapter],
        format: str = "table"
    ) -> None:
        """
        Display chapters to console.

        Args:
            chapters: List of chapters to display
            format: Display format - "table", "tree", or "panel"
        """
        if not chapters:
            self.console.print("[yellow]No chapters to display[/yellow]")
            return

        if format == "tree":
            self.console.print(self.create_tree(chapters))
        elif format == "panel":
            self.console.print(self.create_panel(chapters))
        else:  # table
            self.console.print(self.create_table(chapters))

        # Always show summary
        self.console.print()
        self.console.print(self.create_summary_panel(chapters))

    def export_ffmetadata(
        self,
        chapters: List[Chapter],
        output_path: Path
    ) -> None:
        """
        Export chapters to FFmpeg metadata format.

        Args:
            chapters: List of chapters to export
            output_path: Path to output FFMETADATA file
        """
        lines = [";FFMETADATA1"]

        for chapter in chapters:
            # Convert times to milliseconds
            start_ms = int(chapter.start_time * 1000)
            end_ms = int(chapter.end_time * 1000)

            lines.append("")
            lines.append("[CHAPTER]")
            lines.append("TIMEBASE=1/1000")
            lines.append(f"START={start_ms}")
            lines.append(f"END={end_ms}")
            lines.append(f"title={chapter.title}")

        # Write to file
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines))

    def export_json(
        self,
        chapters: List[Chapter],
        output_path: Path
    ) -> None:
        """
        Export chapters to JSON format.

        Args:
            chapters: List of chapters to export
            output_path: Path to output JSON file
        """
        import json

        chapters_data = []
        for chapter in chapters:
            chapters_data.append({
                "number": chapter.number,
                "title": chapter.title,
                "start_time": chapter.start_time,
                "end_time": chapter.end_time,
                "duration": chapter.duration,
                "start_formatted": Chapter.format_time(chapter.start_time),
                "end_formatted": Chapter.format_time(chapter.end_time),
                "images": [str(p) for p in chapter.image_paths]
            })

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump({
                "total_chapters": len(chapters),
                "chapters": chapters_data
            }, f, indent=2)

    @staticmethod
    def from_scene_extraction_result(result) -> List[Chapter]:
        """
        Create chapter list from SceneExtractionResult.

        Args:
            result: SceneExtractionResult from scene extractor

        Returns:
            List of Chapter instances
        """
        chapters = []
        for scene_info in result.scenes:
            chapter = Chapter.from_scene_info(scene_info)
            chapters.append(chapter)
        return chapters
