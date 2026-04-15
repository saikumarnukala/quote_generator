def _seconds_to_srt_time(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def generate_srt(scenes: list, durations: list, output_path: str) -> str:
    """
    Generate an SRT subtitle file from scene narrations and their audio durations.

    Args:
        scenes:    list of scene dicts, each with a 'narration' key
        durations: list of floats matching scene audio durations (seconds)
        output_path: path to write the .srt file

    Returns:
        output_path
    """
    lines = []
    current_time = 0.0

    for i, (scene, duration) in enumerate(zip(scenes, durations), start=1):
        start = current_time
        end = current_time + duration

        lines.append(str(i))
        lines.append(f"{_seconds_to_srt_time(start)} --> {_seconds_to_srt_time(end)}")
        lines.append(scene["narration"])
        lines.append("")

        current_time = end

    with open(output_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return output_path
