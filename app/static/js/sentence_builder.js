class SentenceBuilder {
    constructor() {}

    /**
     * Group words into sentences based on punctuation.
     * @param {Array} words - Array of {word, start, end} objects
     * @returns {Array} Array of {text, words, start, end} objects
     */
    groupWords(words) {
        return this._groupingLogic(words);
    }

    _groupingLogic(words) {
        const sentences = [];
        let currentWords = [];
        
        for (const w of words) {
            currentWords.push(w);
            const clean = w.word.trim();
            // Check for punctuation
            if (clean.endsWith('.') || clean.endsWith('?') || clean.endsWith('!')) {
                sentences.push(this._createSentence(currentWords));
                currentWords = [];
            }
        }
        
        if (currentWords.length > 0) {
            sentences.push(this._createSentence(currentWords));
        }
        
        return sentences;
    }

    _createSentence(words) {
        if (words.length === 0) return null;
        const text = words.map(w => w.word).join(' ');
        return {
            text: text,
            words: words,
            start: words[0].start,
            end: words[words.length - 1].end
        };
    }

    filterWords(words, startTime, endTime) {
        return words.filter(w => w.start >= startTime && w.end <= endTime);
    }
}

// Export for node testing or attach to window
if (typeof window !== 'undefined') {
    window.SentenceBuilder = SentenceBuilder;
}
if (typeof global !== 'undefined') {
    global.SentenceBuilder = SentenceBuilder;
}
