from pathlib import Path

from intelligence.color_engine import (
    analyze_color_uniformity,
    create_color_heatmap,
)


def main() -> None:
    image_path = Path("test_green.jpg")

    if not image_path.exists():
        raise FileNotFoundError(
            "Lägg en testbild med namnet test_green.jpg i backend-mappen."
        )

    image_bytes = image_path.read_bytes()

    result = analyze_color_uniformity(image_bytes)
    print(result)

    heatmap_bytes = create_color_heatmap(image_bytes)
    Path("test_green_heatmap.jpg").write_bytes(heatmap_bytes)

    print("Heatmap sparad som test_green_heatmap.jpg")


if __name__ == "__main__":
    main()