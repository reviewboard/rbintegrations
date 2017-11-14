(function() {


/**
 * An inline editor view for selecting Trello cards.
 */
const TrelloInlineEditorView = RB.InlineEditorView.extend({
    /**
     * Initialize the view.
     *
     * Args:
     *     options (object):
     *         Options for the view.
     */
    initialize(options) {
        options = _.defaults(options, {
            hasRawValue: true,
            formatResult: value => {
                if (value && value.name) {
                    return value.name.htmlEncode();
                } else {
                    return '';
                }
            },
            getFieldValue: editor => {
                const selectize = this.$field[0].selectize;
                const selected = selectize.getValue();

                return JSON.stringify(
                    selected.map(key => selectize.options[key]));
            },
            isFieldDirty: (editor, initialValue) => {
                const value = editor.getValue();
                return (initialValue !== value);
            },
            setFieldValue: (editor, value) => {
                // This is a no-op, since we do this in the $.selectize call.
            },
        });

        RB.InlineEditorView.prototype.initialize.call(this, options);
    },

    /**
     * Create and return the field to use for the input element.
     *
     * Returns:
     *     jQuery:
     *     The newly created input element.
     */
    createField() {
        return $('<select multiple class="trello-field">');
    },

    /**
     * Connect events.
     */
    setupEvents() {
        RB.InlineEditorView.prototype.setupEvents.call(this);

        this.$field.on('change', this._scheduleUpdateDirtyState.bind(this));
    },

    /**
     * Show the editor.
     *
     * Args:
     *     options (object, optional):
     *         Options for showing the editor.
     */
    showEditor(options={}) {
        RB.InlineEditorView.prototype.showEditor.call(this, options);

        if (this.options.focusOnOpen) {
            this.$field[0].selectize.focus();
        }
    },
});


/**
 * A review request field view for selecting Trello cards.
 */
RB.ReviewRequestFields.TrelloFieldView =
    RB.ReviewRequestFields.TextFieldView.extend({
    autocomplete: {},
    multiline: true,
    useEditIconOnly: true,

    cardTemplate: _.template(dedent`
        <<%- tagName %> class="trello-card">
         <div class="trello-card-card">
          <a href="<%- url %>"><%- name %></a>
         </div>
         <div class="trello-card-details">
          on <span class="trello-card-list"><%- list %></span>
          in <span class="trello-card-board"><%- board %></span>
         </div>
        </<%- tagName %>>
        `),

    /**
     * Format the contents of the field.
     *
     * This will apply the contents of the model attribute to the field
     * element. If the field defines a ``formatValue`` method, this will use
     * that to do the formatting. Otherwise, the element will just be set to
     * contain the text of the value.
     */
    _formatField() {
        const cards = JSON.parse(this.model.getDraftField(
            this.jsonFieldName || this.fieldID, {
                useExtraData: this.useExtraData,
            }));
        this._renderValue(cards);
    },

    /**
     * Render the current value of the field.
     *
     * Args:
     *     cards (Array of object):
     *         The current set of cards to list.
     */
    _renderValue(cards) {
        const items = cards.map(card => this.cardTemplate(_.defaults({
            tagName: 'li',
        }, card)));
        this.$el.html(`<ul>${items.join('')}</ul>`);
    },

    /**
     * Return the type to use for the inline editor view.
     *
     * Returns:
     *     function:
     *     The constructor for the inline editor class to instantiate.
     */
    _getInlineEditorClass() {
        return TrelloInlineEditorView;
    },

    /**
     * Add auto-complete functionality to the field.
     */
    _buildAutoComplete() {
        const reviewRequest = this.model.get('reviewRequest');
        const localSite = reviewRequest.get('localSitePrefix');
        const reviewRequestId = reviewRequest.get('id');
        const url = `${SITE_ROOT}rbintegrations/trello/${localSite}card-search/${reviewRequestId}/`;
        const $field = this.inlineEditorView.$field;
        const cards = this.$el.data('raw-value');

        this._renderValue(cards || []);

        $field.selectize({
            copyClassesToDropdown: true,
            dropdownParent: 'body',
            multiple: true,
            labelField: 'name',
            valueField: 'id',
            searchField: 'name',
            options: cards,
            items: _.pluck(cards, 'id'),
            render: {
                option: (data, escape) => this.cardTemplate(_.defaults({
                    tagName: 'div',
                }, data)),
            },
            load(query, callback) {
                const params = $.param({ q: query });

                $.ajax({
                    url: `${url}?${params}`,
                    type: 'GET',
                    error: callback.bind(this),
                    success: res => callback(res),
                });
            },
        });
    },
});


})();
