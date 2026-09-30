package dev.mygpt.companionv2

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject

/**
 * Android reader for the same AIRI-style MyGPT character card used by Python.
 *
 * The asset is copied from brain/personas at build time. A card is trusted here
 * only because this exact app build explicitly chooses the bundled asset.
 */
data class AndroidCharacterCard(
    val cardId: String,
    val name: String,
    val nickname: String?,
    val visualSkinId: String,
    val personality: String?,
    val scenario: String?,
    val systemPrompt: String?,
    val postHistoryInstructions: String?,
    val greetings: List<String>,
    val messageExamples: List<List<String>>,
) {
    fun renderInstructions(): String {
        val parts = ArrayList<String>()
        parts += "Character identity: " + name + "."
        if (!nickname.isNullOrBlank()) {
            parts += "Nickname: " + nickname + "."
        }
        if (!systemPrompt.isNullOrBlank()) {
            parts += systemPrompt
        }
        if (!personality.isNullOrBlank()) {
            parts += "Personality:\n" + personality
        }
        if (!scenario.isNullOrBlank()) {
            parts += "Scenario:\n" + scenario
        }
        if (!postHistoryInstructions.isNullOrBlank()) {
            parts += "Conversation consistency guidance:\n" + postHistoryInstructions
        }
        if (messageExamples.isNotEmpty()) {
            val examples = messageExamples.take(2).map { it.joinToString("\n") }
            parts += "Approved behavior examples:\n" + examples.joinToString("\n---\n")
        }

        val rendered = parts.joinToString("\n\n")
        require(rendered.length <= 4000) { "rendered persona instructions too long" }
        return rendered
    }

    companion object {
        private const val ASSET = "3714430278.json"
        private const val MAX_BYTES = 65536
        private const val EXPECTED_SCHEMA = "mygpt.character-card.v1"
        private const val EXPECTED_CARD = "mygpt-3714430278"
        private const val EXPECTED_SKIN = "3714430278"

        private val ALLOWED_FIELDS = setOf(
            "schema_version",
            "card_id",
            "name",
            "nickname",
            "version",
            "visual_skin_id",
            "personality",
            "scenario",
            "system_prompt",
            "post_history_instructions",
            "greetings",
            "greetings_group_only",
            "tags",
            "message_examples",
            "source",
            "metadata",
        )

        fun loadApproved(context: Context): AndroidCharacterCard {
            val bytes = context.assets.open(ASSET).use { input ->
                val raw = input.readBytes()
                require(raw.size <= MAX_BYTES) { "character card exceeds size limit" }
                raw
            }
            val root = JSONObject(bytes.toString(Charsets.UTF_8))
            val keys = root.keys().asSequence().toSet()
            require(keys.all { it in ALLOWED_FIELDS }) { "character card has unknown fields" }

            require(root.getString("schema_version") == EXPECTED_SCHEMA)
            require(root.getString("card_id") == EXPECTED_CARD)
            require(root.getString("visual_skin_id") == EXPECTED_SKIN)

            val name = checkedText(root.getString("name"), 80, false)
            val nickname = root.optString("nickname", "").takeIf { it.isNotBlank() }
                ?.let { checkedText(it, 80, false) }

            val greetings = readStrings(root.optJSONArray("greetings"), 16, 1000)
            val examples = readExamples(root.optJSONArray("message_examples"))

            return AndroidCharacterCard(
                cardId = EXPECTED_CARD,
                name = name,
                nickname = nickname,
                visualSkinId = EXPECTED_SKIN,
                personality = optionalText(root, "personality", 2000),
                scenario = optionalText(root, "scenario", 2000),
                systemPrompt = optionalText(root, "system_prompt", 3000),
                postHistoryInstructions = optionalText(
                    root,
                    "post_history_instructions",
                    2000,
                ),
                greetings = greetings,
                messageExamples = examples,
            )
        }

        private fun optionalText(
            root: JSONObject,
            key: String,
            maxChars: Int,
        ): String? {
            if (!root.has(key) || root.isNull(key)) return null
            val value = root.getString(key)
            return checkedText(value, maxChars, true)
        }

        private fun checkedText(
            value: String,
            maxChars: Int,
            allowEmpty: Boolean,
        ): String {
            require(value == value.trim()) { "character card text must be trimmed" }
            if (!allowEmpty) require(value.isNotEmpty()) { "character card text is blank" }
            require(value.length <= maxChars) { "character card text too long" }
            require(value.none { it.code < 32 && it != '\n' && it != '\t' }) {
                "character card text has control characters"
            }
            return value
        }

        private fun readStrings(
            value: JSONArray?,
            maxItems: Int,
            maxChars: Int,
        ): List<String> {
            if (value == null) return emptyList()
            require(value.length() <= maxItems) { "character card list too large" }
            val result = ArrayList<String>()
            for (index in 0 until value.length()) {
                val item = checkedText(value.getString(index), maxChars, false)
                if (item !in result) result += item
            }
            return result
        }

        private fun readExamples(value: JSONArray?): List<List<String>> {
            if (value == null) return emptyList()
            require(value.length() <= 16) { "too many character examples" }
            val result = ArrayList<List<String>>()

            for (groupIndex in 0 until value.length()) {
                val group = value.getJSONArray(groupIndex)
                require(group.length() in 1..16) { "invalid example group size" }
                val lines = ArrayList<String>()

                for (lineIndex in 0 until group.length()) {
                    val line = checkedText(group.getString(lineIndex), 1000, false)
                    require(
                        line.startsWith("{{char}}: ")
                            || line.startsWith("{{user}}: ")
                    ) { "invalid character example protocol" }
                    lines += line
                }
                result += lines
            }
            return result
        }
    }
}
