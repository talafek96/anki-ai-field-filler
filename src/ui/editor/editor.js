/**
 * AI Filler Integrated Editor Script
 * Manages the injection and behavior of the prompt field.
 * Optimized for Anki 25.09+ (Svelte based editor).
 */

(function() {
    if (window.aiFiller) return;

    window.aiFiller = {
        container: null,
        textarea: null,
        isCollapsed: false,

        /**
         * Initialize the prompt field in the DOM.
         */
        init: function(isExpanded = true) {
            if (this.container && document.contains(this.container)) {
                return;
            }

            const fields = document.querySelector('.fields') || 
                           document.querySelector('.fields-container') || 
                           document.getElementById('fields');

            if (!fields) {
                setTimeout(() => this.init(isExpanded), 100);
                return;
            }

            this.isCollapsed = !isExpanded;

            const container = document.createElement('div');
            container.id = 'ai-filler-prompt-container';
            if (this.isCollapsed) {
                container.classList.add('ai-filler-collapsed');
            }
            
            container.innerHTML = `
                <div class="ai-filler-prompt-header">
                    <span class="ai-filler-prompt-label">
                        AI PROMPT
                    </span>
                    <div class="ai-filler-header-actions">
                        <button id="ai-filler-undo-btn" class="ai-filler-nav-btn" title="Undo AI Fill">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="15 18 9 12 15 6"></polyline>
                            </svg>
                        </button>
                        <button id="ai-filler-redo-btn" class="ai-filler-nav-btn" title="Redo AI Fill">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="9 18 15 12 9 6"></polyline>
                            </svg>
                        </button>
                        <button id="ai-filler-gear-btn" class="ai-filler-nav-btn" title="Select Target Fields">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                                <circle cx="12" cy="12" r="3"></circle>
                                <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                            </svg>
                        </button>
                        <button id="ai-filler-toggle-btn" class="ai-filler-close-btn" title="Collapse/Expand">
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                                <polyline points="18 15 12 9 6 15"></polyline>
                            </svg>
                        </button>
                    </div>
                </div>
                <div class="ai-filler-prompt-body">
                    <textarea 
                        id="ai-filler-prompt-textarea" 
                        placeholder="Add instructions or leave blank to fill context-awarely..."
                        spellcheck="false"
                    ></textarea>
                    <button id="ai-filler-generate-btn" class="ai-filler-btn-primary">
                        ${window.aiFillerSparkleSVG || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.912 5.813L21 10.725l-5.813 1.912L12 21l-1.912-5.813L3 13.275l5.813-1.912L12 3z"></path></svg>'}
                        Generate
                    </button>
                </div>
            `;

            fields.insertBefore(container, fields.firstChild);
            this.container = container;
            this.textarea = document.getElementById('ai-filler-prompt-textarea');

            document.getElementById('ai-filler-toggle-btn').addEventListener('click', () => this.toggleCollapse());
            document.getElementById('ai-filler-generate-btn').addEventListener('click', () => this.onGenerate());
            document.getElementById('ai-filler-undo-btn').addEventListener('click', () => this.onUndo());
            document.getElementById('ai-filler-redo-btn').addEventListener('click', () => this.onRedo());
            document.getElementById('ai-filler-gear-btn').addEventListener('click', () => this.onSelectFields());

            this.textarea.addEventListener('keydown', (e) => {
                if (e.key === 'Enter') {
                    if (e.shiftKey) {
                        return;
                    } else {
                        e.preventDefault();
                        this.onGenerate();
                    }
                }
            });
        },

        toggleCollapse: function() {
            if (!this.container || !document.contains(this.container)) {
                this.init();
            }
            
            this.isCollapsed = !this.isCollapsed;
            
            if (this.isCollapsed) {
                this.container.classList.add('ai-filler-collapsed');
            } else {
                this.container.classList.remove('ai-filler-collapsed');
                this.textarea.focus();
            }

            pycmd("ai_filler:save_collapsed_state:" + this.isCollapsed);
        },

        onGenerate: function() {
            const prompt = this.textarea.value.trim();
            const btn = document.getElementById('ai-filler-generate-btn');
            
            btn.classList.add('ai-filler-btn-loading');
            const originalHTML = btn.innerHTML;
            btn.innerHTML = 'Generating...';
            btn.disabled = true;
            
            pycmd("ai_filler:generate:" + prompt);
            
            setTimeout(() => {
                btn.classList.remove('ai-filler-btn-loading');
                btn.innerHTML = originalHTML;
                btn.disabled = false;
            }, 5000); 
        },

        onUndo: function() {
            pycmd("ai_filler:undo");
        },

        onRedo: function() {
            pycmd("ai_filler:redo");
        },

        onSelectFields: function() {
            pycmd("ai_filler:select_fields");
        },

        updateButton: function(mode) {
            const btn = document.getElementById('ai-filler-generate-btn');
            if (!btn) return;
            
            const isModify = mode === 'modify';
            const label = isModify ? 'Modify' : 'Generate';
            
            const svg = window.aiFillerSparkleSVG || '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 3l1.912 5.813L21 10.725l-5.813 1.912L12 21l-1.912-5.813L3 13.275l5.813-1.912L12 3z"></path></svg>';
            
            btn.innerHTML = `${svg} ${label}`;
            btn.setAttribute('data-mode', mode);
        },

        setPrompt: function(text) {
            if (!this.textarea) this.init();
            this.textarea.value = text;
        }
    };

    aiFiller.init();
})();
