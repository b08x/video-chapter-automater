"""
Pipeline orchestration module for VideoChapterAutomater.

Coordinates multi-stage preprocessing workflows with progress tracking,
error handling, and result consolidation.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Optional, Any

from rich.console import Console
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeElapsedColumn,
)
from rich.panel import Panel
from rich.table import Table

from ..output.manager import OutputManager, OutputType
from .config import PipelineConfig, PipelineStage, ExecutionMode
from .stage import Stage, StageResult, StageStatus

console = Console()


@dataclass
class PipelineResult:
    """
    Result from executing a complete pipeline.

    Attributes:
        success: Whether pipeline completed successfully
        total_duration: Total execution time in seconds
        stage_results: Results from each executed stage
        input_path: Original input file path
        output_paths: Dictionary mapping output types to paths
        metadata: Additional pipeline metadata
        error_summary: Summary of any errors encountered
    """
    success: bool
    total_duration: float
    stage_results: List[StageResult] = field(default_factory=list)
    input_path: Optional[Path] = None
    output_paths: Dict[str, Path] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    error_summary: Optional[str] = None

    @property
    def completed_stages(self) -> List[StageResult]:
        """Get list of successfully completed stages."""
        return [r for r in self.stage_results if r.status == StageStatus.COMPLETED]

    @property
    def failed_stages(self) -> List[StageResult]:
        """Get list of failed stages."""
        return [r for r in self.stage_results if r.status == StageStatus.FAILED]

    @property
    def skipped_stages(self) -> List[StageResult]:
        """Get list of skipped stages."""
        return [r for r in self.stage_results if r.status == StageStatus.SKIPPED]

    def get_stage_result(self, stage: PipelineStage) -> Optional[StageResult]:
        """
        Get result for a specific stage.

        Args:
            stage: Stage to get result for

        Returns:
            StageResult if found, None otherwise
        """
        for result in self.stage_results:
            if result.stage == stage:
                return result
        return None

    def __repr__(self) -> str:
        """String representation of pipeline result."""
        return (
            f"PipelineResult("
            f"success={self.success}, "
            f"stages={len(self.stage_results)}, "
            f"duration={self.total_duration:.2f}s)"
        )


class PipelineOrchestrator:
    """
    Orchestrates multi-stage preprocessing pipelines.

    Manages execution flow, progress tracking, error handling, and result
    consolidation across multiple preprocessing stages.
    """

    def __init__(
        self,
        config: PipelineConfig,
        output_manager: Optional[OutputManager] = None,
        verbose: bool = False
    ):
        """
        Initialize pipeline orchestrator.

        Args:
            config: Pipeline configuration
            output_manager: Output directory manager (creates default if None)
            verbose: Enable verbose output
        """
        self.config = config
        self.verbose = verbose

        # Validate configuration
        self.config.validate()

        # Initialize output manager
        if output_manager is None:
            output_manager = OutputManager(
                base_dir=config.output_base_dir,
                project_name=config.project_name,
                auto_create=True
            )
        self.output_manager = output_manager

        # Create stages
        self.stages = self._create_stages()

    def _create_stages(self) -> List[Stage]:
        """
        Create Stage instances from configuration.

        Returns:
            List of configured Stage objects
        """
        stages = []
        for stage_config in self.config.stages:
            stage = Stage(stage_config, verbose=self.verbose)
            stages.append(stage)
        return stages

    def execute(self, input_path: Path, **kwargs) -> PipelineResult:
        """
        Execute complete pipeline on input file.

        Args:
            input_path: Path to input video file
            **kwargs: Additional arguments passed to stages

        Returns:
            PipelineResult with execution details
        """
        start_time = time.time()

        # Validate input
        if not input_path.exists():
            return PipelineResult(
                success=False,
                total_duration=0.0,
                input_path=input_path,
                error_summary=f"Input file does not exist: {input_path}"
            )

        # Display pipeline start
        if self.config.enable_progress_bars:
            self._display_pipeline_header(input_path)

        # Copy source file if requested
        if self.config.copy_source:
            self._copy_source_file(input_path)

        # Execute based on mode
        if self.config.execution_mode == ExecutionMode.SEQUENTIAL:
            stage_results = self._execute_sequential(input_path, **kwargs)
        elif self.config.execution_mode == ExecutionMode.RESILIENT:
            stage_results = self._execute_resilient(input_path, **kwargs)
        else:
            # PARALLEL mode - future enhancement
            stage_results = self._execute_sequential(input_path, **kwargs)

        # Calculate total duration
        total_duration = time.time() - start_time

        # Determine overall success
        success = all(r.success or r.status == StageStatus.SKIPPED for r in stage_results)

        # Collect output paths
        output_paths = self._collect_output_paths(stage_results)

        # Generate error summary if needed
        error_summary = None
        if not success:
            error_summary = self._generate_error_summary(stage_results)

        # Generate manifest
        if success:
            self._generate_manifest(input_path, stage_results, total_duration)

        # Display completion summary
        if self.config.enable_progress_bars:
            self._display_completion_summary(stage_results, total_duration, success)

        return PipelineResult(
            success=success,
            total_duration=total_duration,
            stage_results=stage_results,
            input_path=input_path,
            output_paths=output_paths,
            metadata={
                "execution_mode": self.config.execution_mode.value,
                "num_stages": len(self.stages),
            },
            error_summary=error_summary
        )

    def _execute_sequential(self, input_path: Path, **kwargs) -> List[StageResult]:
        """
        Execute stages sequentially.

        Args:
            input_path: Input file path
            **kwargs: Additional arguments

        Returns:
            List of stage results
        """
        stage_results = []
        current_input = input_path

        # Setup progress tracking
        if self.config.enable_progress_bars:
            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                console=console
            ) as progress:
                task = progress.add_task(
                    "[cyan]Processing pipeline...",
                    total=len(self.stages)
                )

                for stage in self.stages:
                    # Update progress
                    progress.update(
                        task,
                        description=f"[cyan]{stage.get_operation_name()}..."
                    )

                    # Execute stage
                    result = self._execute_stage(stage, current_input, **kwargs)
                    stage_results.append(result)

                    # Update progress
                    progress.advance(task)

                    # Handle errors
                    if result.status == StageStatus.FAILED:
                        if self.config.stop_on_error:
                            # Skip remaining stages
                            for remaining_stage in self.stages[len(stage_results):]:
                                skipped = StageResult(
                                    stage=remaining_stage.config.stage,
                                    status=StageStatus.SKIPPED,
                                    metadata={"reason": "Previous stage failed"}
                                )
                                stage_results.append(skipped)
                            break
                        elif not stage.config.skip_on_error:
                            break

                    # Update input for next stage only if this is a video transformation stage
                    # currently only video_encoding produces a video for subsequent stages
                    if stage.config.stage == PipelineStage.VIDEO_ENCODING:
                        if result.output_path and result.output_path.exists() and result.output_path.is_file():
                            current_input = result.output_path
        else:
            # Execute without progress bars
            for stage in self.stages:
                result = self._execute_stage(stage, current_input, **kwargs)
                stage_results.append(result)

                if result.status == StageStatus.FAILED and self.config.stop_on_error:
                    break

                if stage.config.stage == PipelineStage.VIDEO_ENCODING:
                    if result.output_path and result.output_path.exists() and result.output_path.is_file():
                        current_input = result.output_path

        return stage_results

    def _execute_resilient(self, input_path: Path, **kwargs) -> List[StageResult]:
        """
        Execute stages with resilience (continue on errors).

        Args:
            input_path: Input file path
            **kwargs: Additional arguments

        Returns:
            List of stage results
        """
        # Same as sequential but never stops on error
        original_stop_on_error = self.config.stop_on_error
        self.config.stop_on_error = False

        results = self._execute_sequential(input_path, **kwargs)

        self.config.stop_on_error = original_stop_on_error
        return results

    def _execute_stage(self, stage: Stage, input_path: Path, **kwargs) -> StageResult:
        """
        Execute a single pipeline stage.

        Args:
            stage: Stage to execute
            input_path: Input file path
            **kwargs: Additional arguments

        Returns:
            StageResult from execution
        """
        # Determine output directory for stage
        output_dir = self._get_stage_output_dir(stage)

        # Execute stage
        return stage.execute(input_path, output_dir=output_dir, **kwargs)

    def _get_stage_output_dir(self, stage: Stage) -> Optional[Path]:
        """
        Get output directory for a specific stage.

        Args:
            stage: Stage to get output directory for

        Returns:
            Path to output directory or None
        """
        # Map stages to output types
        output_type_map = {
            PipelineStage.VIDEO_ENCODING: OutputType.VIDEO,
            PipelineStage.AUDIO_EXTRACTION: OutputType.AUDIO,
            PipelineStage.SCENE_EXTRACTION: OutputType.SCENES,
        }

        output_type = output_type_map.get(stage.config.stage)
        if output_type:
            return self.output_manager.get_subdir(output_type)

        return None

    def _collect_output_paths(self, stage_results: List[StageResult]) -> Dict[str, Path]:
        """
        Collect output paths from all stages.

        Args:
            stage_results: List of stage results

        Returns:
            Dictionary mapping stage names to output paths
        """
        output_paths = {}
        for result in stage_results:
            if result.output_path:
                output_paths[result.stage.value] = result.output_path
        return output_paths

    def _generate_error_summary(self, stage_results: List[StageResult]) -> str:
        """
        Generate summary of errors from failed stages.

        Args:
            stage_results: List of stage results

        Returns:
            Error summary string
        """
        failed = [r for r in stage_results if r.status == StageStatus.FAILED]

        if not failed:
            return "No errors"

        summary_lines = [f"Pipeline failed with {len(failed)} stage error(s):"]
        for result in failed:
            summary_lines.append(f"  - {result.stage.value}: {result.error_message}")

        return "\n".join(summary_lines)

    def _generate_manifest(
        self,
        input_path: Path,
        stage_results: List[StageResult],
        duration: float
    ) -> None:
        """
        Generate pipeline execution manifest.

        Args:
            input_path: Original input file
            stage_results: List of stage results
            duration: Total execution duration
        """
        outputs = {}
        stats = {}

        for result in stage_results:
            if result.output_path:
                outputs[result.stage.value] = result.output_path

            stats[result.stage.value] = {
                "status": result.status.value,
                "duration": result.duration,
            }

        self.output_manager.generate_manifest(
            video_name=input_path.stem,
            outputs=outputs,
            stats={
                "total_duration": duration,
                "stages": stats,
            }
        )

    def _display_pipeline_header(self, input_path: Path) -> None:
        """Display pipeline execution header."""
        table = Table(title="Pipeline Configuration")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="green")

        table.add_row("Input File", str(input_path.name))
        table.add_row("Execution Mode", self.config.execution_mode.value)
        table.add_row("Output Directory", str(self.output_manager.base_dir))
        table.add_row("Enabled Stages", str(len(self.config.get_enabled_stages())))

        console.print(table)
        console.print()

    def _display_completion_summary(
        self,
        stage_results: List[StageResult],
        duration: float,
        success: bool
    ) -> None:
        """
        Display pipeline completion summary.

        Args:
            stage_results: List of stage results
            duration: Total duration
            success: Whether pipeline succeeded
        """
        # Create results table
        table = Table(title="Pipeline Execution Summary")
        table.add_column("Stage", style="cyan")
        table.add_column("Status", style="bold")
        table.add_column("Duration", style="magenta")
        table.add_column("Output", style="green")

        for result in stage_results:
            # Status with color
            if result.status == StageStatus.COMPLETED:
                status = "[green]✓ Completed[/green]"
            elif result.status == StageStatus.FAILED:
                status = "[red]✗ Failed[/red]"
            elif result.status == StageStatus.SKIPPED:
                status = "[yellow]⊘ Skipped[/yellow]"
            else:
                status = f"[dim]{result.status.value}[/dim]"

            # Output path
            output = str(result.output_path.name) if result.output_path else "-"

            table.add_row(
                result.stage.value,
                status,
                f"{result.duration:.2f}s",
                output
            )

        console.print()
        console.print(table)

        # Overall summary panel
        summary_color = "green" if success else "red"
        summary_symbol = "✓" if success else "✗"
        summary_text = f"[{summary_color}]{summary_symbol} Pipeline {'Completed' if success else 'Failed'}[/{summary_color}]"
        summary_text += f"\nTotal Duration: {duration:.2f}s"

        console.print()
        console.print(Panel(summary_text, title="Result", border_style=summary_color))
        console.print()

    def estimate_total_duration(self, input_path: Path) -> float:
        """
        Estimate total pipeline execution duration.

        Args:
            input_path: Input file path

        Returns:
            Estimated duration in seconds
        """
        total = 0.0
        for stage in self.stages:
            if stage.config.enabled:
                total += stage.estimate_duration(input_path)
        return total

    def _copy_source_file(self, input_path: Path) -> None:
        """
        Copy source file to project directory.

        Args:
            input_path: Path to source file
        """
        try:
            source_dir = self.output_manager.get_subdir(OutputType.SOURCE)
            dest_path = source_dir / input_path.name
            
            if self.verbose:
                console.print(f"[dim]Copying source file to {dest_path}...[/dim]")
                
            import shutil
            shutil.copy2(input_path, dest_path)
        except Exception as e:
            console.print(f"[yellow]Warning: Failed to copy source file: {e}[/yellow]")

    def __repr__(self) -> str:
        """String representation of orchestrator."""
        return (
            f"PipelineOrchestrator("
            f"stages={len(self.stages)}, "
            f"mode={self.config.execution_mode.value})"
        )
