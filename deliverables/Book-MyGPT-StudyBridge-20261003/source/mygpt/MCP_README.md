# Book / mygpt 鏈満 MCP 璇曢獙鐗?
**杩欐槸鍙繍琛岀殑鏈満 MCP 2.0 鏈嶅姟锛屼笉鏄湡姝?Your dot 宸叉帴閫氱殑璇佹槑銆?* 涓嶆敼 Book EXE銆佷笉鏀归槄璇诲瓧鍙锋垨棰勪範/瀛︿範/澶嶄範/鍒烽娴佺▼锛涙病鏈夊叕缃戠鍙ｃ€佽嚜鍔ㄥ惎鍔ㄣ€佹ā鍨嬭皟鐢ㄣ€佽闊虫垨 Live 灞曠ず銆?
## 鍚姩

鍦ㄥ綋鍓嶅凡鏍搁獙鐨?Windows 宸ヤ綔鍖猴紝鐢?PowerShell 鎵ц鏈枃浠跺悓鐩綍鐨?`Start-MCP.ps1`銆傞粯璁?`http://127.0.0.1:8766/mcp`锛涚鍙ｅ崰鐢ㄦ椂浼?`-Port 鍏朵粬绔彛`銆侰trl+C 鍋滄銆?
鑴氭湰浣跨敤鐜版湁 `work/mygpt-progress-venv` 鍜屽浐瀹氭彁浜ょ殑 mygpt brain锛涢娆″惎鍔ㄥ湪 `work/mcp-prototype/runtime` 鍒涘缓涓や釜鐙珛闅忔満浠ょ墝锛屼粎褰撳墠鐢ㄦ埛涓?SYSTEM 鑾峰緱璇ョ洰褰曟潈闄愩€備笉鎶婁护鐗屾墦鍗般€佸啓杩涙簮鐮併€佹彁浜?GitHub 鎴栦笂浼?Drive銆俙-PrepareOnly` 鍙噯澶囪繍琛岀洰褰曪紝涓嶅惎鍔ㄦ湇鍔°€?
鏈洰褰曟槸 mygpt 鐨勫閲忔簮浠ｇ爜锛屼笉鏄畬鏁村彂琛屽寘銆傝縼绉诲埌鍙︿竴鍙扮數鑴戞椂搴旀妸澧為噺鏀惧叆鐜版湁 mygpt 椤圭洰锛岃缃?`MYGPT_SOURCE_ROOT` 鍒板叾 brain 鐩綍锛屽苟鍦ㄧ嫭绔嬭櫄鎷熺幆澧冨畨瑁?`requirements-mcp.txt`銆備笉瑕佹妸娴嬭瘯鐢ㄤ护鐗屾毚闇插埌鍏綉銆?
## 宸插疄鐜扮殑鎺ュ彛

- `POST /mcp`锛氬崗璁?`2026-07-28`锛屽彧鏈変袱涓獎鏉冮檺宸ュ叿锛?  - `get_study_progress({})`锛氳鍙栧皻鏈繃鏈熺殑鏈€灏忚繘搴︿笌鏈嶅姟鍣ㄦ椂闂淬€?  - `submit_study_decision({decision_id,producer_session,progress_sequence,action,objective})`锛歚action` 涓?`stay_quiet` 鎴?`speak`锛涘畨闈欐椂 objective 蹇呴』 null锛涙帓闃熻€屼笉鍚姩妯″瀷鎴?Live銆?- `POST /local/progress`锛歮ygpt 鎻愪氦鏃㈡湁 `BookProgress` wire 瀵硅薄锛屼笉鎺ュ彈姝ｆ枃/绗旇/绛旀绛夐澶栧瓧娈点€?- `POST /local/decisions/take`锛歮ygpt 鍙栦竴娆″綋鍓嶆湁鏁堢殑鍐崇瓥鍊欓€夛紱鍐嶆鏍￠獙浼氳瘽銆佸簭鍙峰拰鏈夋晥鏈熴€?- `POST /local/disconnect`锛氭竻绌鸿繘搴︿笌寰呮墽琛屽喅绛栥€?- `GET /health`锛氶壌鏉冨悗浠呰繑鍥炴湰鏈虹姸鎬侊紝涓嶅惈姝ｆ枃銆佽繘搴﹁鎯呮垨浠ょ墝銆?
`/mcp` 鍜?`/health` 浣跨敤 `MCP_BRIDGE_TOKEN`锛沗/local/*` 鍙帴鍙楀彟涓€涓?`MYGPT_INGEST_TOKEN`銆侸SON 杩炴帴鎻忚堪 `mcp-connection.example.json` 浠呬緵鏈湴瀹㈡埛绔娇鐢紝涓嶆槸 Codex/ChatGPT 鎻掍欢娉ㄥ唽閰嶇疆銆?
`LocalMcpBridgeClient.report()` 鐨勬垚鍔熷彧琛ㄧず鏈湴鎺ユ敹銆備笉瑕佹妸瀹冪洿鎺ュ啋鍏呯湡瀹?`DotPort`锛屽惁鍒欐棫 relay 鐨?`reported_to_dot` 鏍囩浼氳瀵笺€傛ā鍨嬩笌 Live 閫傞厤鍣ㄤ粛鏈粦瀹氾紱鍙栧嚭鐨勫喅绛栧繀椤荤敱鏈潵鐪熷疄涓绘満璁よ瘉鏉ユ簮锛屽啀浜ょ幇鏈?relay 澶嶉獙銆?
## 浜嬩欢璇曢獙

浠呭湪鍚姩鏃舵樉寮忔寚瀹?`-AllowLocalTestCallback http://127.0.0.1:鎺ユ敹鍣ㄧ鍙?hook` 鎵嶅紑鍚?Events 鑳藉姏銆傚疄鐜?`events/list`銆乣events/subscribe`銆乣events/unsubscribe`锛涜繃婊ゅ綋鍓?`producer_session`锛屽崟璁㈤槄銆佹湁闄?TTL銆佽闃呰惤鐩樸€佺鍚?challenge銆丼tandard Webhooks 绛惧悕銆佹渶澶氫笁娆￠噸璇曞拰瀵嗛挜杞崲銆?
瀹冨彧鍚戣繖涓€鏉℃槑纭厑璁哥殑鏈湴鍦板潃鍙戦€侊紝涓嶆帴鍙椾换鎰忎富鏈恒€佷唬鐞嗘垨閲嶅畾鍚戙€侶TTP 鍥炶皟鏄?**鏈湴璇曢獙渚嬪**锛屼笉婊¤冻鐪熷疄 dot 瑕佹眰鐨勫叕缃?HTTPS/OAuth銆傞槄璇昏繘搴﹀拰鍐崇瓥鍙繚瀛樺湪鍐呭瓨锛岃繘绋嬮噸鍚笉澶嶆椿鏃ц繘搴︼紱纾佺洏璁㈤槄鍖呭惈鏈湴娴嬭瘯绛惧悕瀵嗛挜锛屼笉瑕佸叡浜繍琛岀洰褰曘€?
杩涘害鏈夋晥鏈熸渶澶?15 绉掋€傚紓姝ユ敹鍒颁簨浠跺悗锛岃鍏堢敤 `get_study_progress` 璇诲彇褰撳墠鐘舵€侊紝鍐嶆彁浜ゅ搴旂殑鏂板喅绛栵紝涓嶈兘寤堕暱鏃ц繘搴︽潵楠楄繃鏃舵晥楠岃瘉銆傞噸澶?decision_id 涓嶉噸澶嶅叆闃燂紱鍏抽棴銆佸け鏁堟垨鍒囨崲浼氳瘽鍚庢嫆缁濇棫鍐冲畾銆傞€€褰逛細璇濆彧淇濆瓨鏈€澶?128 涓憳瑕侊紝杈惧埌闄愬埗鍚庨』鏄惧紡閲嶅惎妗ユ帴锛屼笉鑷姩娣樻卑閲嶆斁闃叉姢淇℃伅銆?
## 楠岃瘉鑼冨洿

楠岃瘉浣跨敤鐙珛鐪熷疄 HTTP 瀛愯繘绋嬨€佹祴璇曞洖璋冩帴鏀跺櫒鍜屽畼鏂?`@modelcontextprotocol/client@2.2.0`锛汼DK 鏄庣‘ pin `2026-07-28` modern 妯″紡銆傛祴璇曡处鎴?杈撳叆鏄槑纭爣璁扮殑鍚堟垚鏁版嵁锛屼笉鏄?dot銆佺湡瀹炴ā鍨嬫垨 Live2D銆?
褰撳墠宸ヤ綔鍖虹殑娴嬭瘯鍏ュ彛涓?`work/mcp-prototype/probe-mcp-capability.cjs`锛屾牳蹇?瀹㈡埛绔祴璇曞湪鍚岀洰褰?`test_mcp_bridge_core.py`銆乣test_mcp_bridge_client.py`銆傛渶缁堝疄闄呭懡浠ゃ€佽緭鍑恒€侀€€鍑虹爜鍜屽け璐ヤ慨澶嶈褰曠粺涓€杩藉姞鑷冲師 `outputs/VERIFICATION.txt`銆傚熀绾挎病鏈夎繖浜?MCP 鏂囦欢锛涘洖婊氬垹闄ゆ柊澧?MCP 鏂囦欢骞舵仮澶嶅師 Book 瀛楄妭銆傚洓瑙掕壊鏂囦欢淇濇寔鍚屼竴缁勩€?
## 鐪熸鎺ュ叆 Your dot 杩樺樊浠€涔?
1. 鏈夌敤鎴锋巿鏉冪殑 OAuth 涓庣ǔ瀹?HTTPS 浜嬩欢鏈嶅姟/鎻掍欢娉ㄥ唽锛岃€岄潪鏈湴 bearer 鍐掑厖 dot銆?2. 瑙傚療鐪熷疄璁㈤槄銆佺鍚嶅洖璋冩帴鏀朵互鍙婄湡瀹?dot 鐨勫伐鍏峰喅绛栵紱HTTP 2xx 涓嶆槸 dot 宸插洖澶嶃€?3. 缁戝畾瀹為檯 mygpt 妯″瀷涓庣幇鏈?Live 鐨勬枃瀛楀睍绀?ACK/鍥炲鎺ュ彛锛屽畬鎴愪竴娆＄湡瀹炰娇鐢ㄩ摼璺€?
鍙傝€冿細[OpenAI MCP Events](https://developers.openai.com/plugins/build/mcp-events)銆乕MCP 2.0 HTTP](https://modelcontextprotocol.io/specification/2026-07-28/basic/transports/streamable-http)銆乕瀹樻柟 SDK](https://github.com/modelcontextprotocol/typescript-sdk)銆乕Standard Webhooks](https://github.com/standard-webhooks/standard-webhooks)銆備笂涓€杞煡鍒扮殑灏忓瀷 starter 浠呯敤浜庡崗璁疄鐜版€濊矾姣旇緝锛屾湭灏嗗叾 demo 瀹ｇО涓?dot 杩炴帴鍣ㄣ€?
