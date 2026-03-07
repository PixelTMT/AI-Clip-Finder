import json
from typing import List
from app.api.models import SubtitleWord


class SubtitleService:
    def load_raw_transcript(self, file_path: str) -> List[SubtitleWord]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return [SubtitleWord(**w) for w in data.get("words", [])]
        except FileNotFoundError:
            return []
        except Exception:
            return []

    def filter_by_timerange(
        self, words: List[SubtitleWord], start_time: float, end_time: float
    ) -> List[SubtitleWord]:
        """
        Filter words to strictly those within the time range.
        """
        return [w for w in words if w.start >= start_time and w.end <= end_time]

    def group_into_sentences(
        self, words: List[SubtitleWord]
    ) -> List[List[SubtitleWord]]:
        sentences = []
        current_sentence = []

        for word in words:
            current_sentence.append(word)
            clean_word = word.word.strip()
            if clean_word and clean_word[-1] in [".", "?", "!"]:
                sentences.append(current_sentence)
                current_sentence = []

        if current_sentence:
            sentences.append(current_sentence)

        return sentences

    def generate_animated_ass(self, words: List[SubtitleWord], options: dict) -> str:
        """
        Generates an .ass subtitle file content where sentences are shown,
        and each word 'pops' as it is spoken.
        """
        bg_color = options.get("bg_color", "&H000000FF")
        text_color = options.get("text_color", "&H00FFFFFF")
        font_size = options.get("font_size", 48)
        pulse_scale = options.get("pulse_scale", 1.2)
        alignment = options.get("alignment", 2)

        # Dimmed color for non-active words (70% transparent white or similar)
        # We'll use the provided text_color but add some transparency if possible,
        # or just a gray color. Let's assume text_color is &H00BBGGRR.
        dimmed_color = "&H99FFFFFF"  # Transparent white for inactive words

        ass_lines = [
            "[Script Info]",
            "Title: Animated Subtitles",
            "ScriptType: v4.00+",
            "PlayResX: 1920",
            "PlayResY: 1080",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
            f"Style: Default,Arial,{font_size},&H00FFFFFF,&H000000FF,&H00000000,&H00000000,1,0,0,0,100,100,0,0,1,2,2,{alignment},10,10,10,1",
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]

        def format_time(seconds: float) -> str:
            h = int(seconds // 3600)
            m = int((seconds % 3600) // 60)
            s = seconds % 60
            return f"{h}:{m:02d}:{s:05.2f}"

        # Group words into sentences
        sentences = self.group_into_sentences(words)

        for sentence in sentences:
            if not sentence:
                continue

            # For each word in the sentence, we create a line that shows the whole sentence,
            # but highlights the current word.
            for i, word in enumerate(sentence):
                w_start = format_time(word.start)
                w_end = format_time(word.end)

                # Animation tags for the active word
                mid_time = (word.end - word.start) / 2 * 1000
                total_ms = (word.end - word.start) * 1000

                # Highlight tags: Pulse + Color + Border
                # We use \r to reset style if needed, but here we'll just inject tags.
                # Highlight Tag: {\1c<text_color>\3c<bg_color>\bord4\t(0,mid,\fscx110\fscy110)\t(mid,total,\fscx100\fscy100)}
                # Note: fscx/fscy inside a sentence will shift other words.
                # To avoid jitter, we'll use Color + Border + Shadow for the "pop".

                # POP = Bold + Color + Border
                pop_tags = f"{{\\c{text_color}\\3c{bg_color}\\bord6\\shad2}}"
                reset_tags = f"{{\\c{dimmed_color}\\bord2\\shad0}}"

                # Build the text: [Dimmed]Word1 [Highlight]Word2 [Dimmed]Word3
                parts = []
                for j, w in enumerate(sentence):
                    if i == j:
                        # Active word
                        parts.append(f"{pop_tags}{w.word}")
                    else:
                        # Inactive word
                        parts.append(f"{reset_tags}{w.word}")

                # Joining with space
                display_text = " ".join(parts)

                # Add the line
                ass_lines.append(
                    f"Dialogue: 1,{w_start},{w_end},Default,,0,0,0,,{reset_tags}{display_text}"
                )

        return "\n".join(ass_lines)
