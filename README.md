chatvdvoem-client
=================

Chatvdvoem client library

Example usage:

    from chatvdvoem import Chatter
    c = Chatter(chat_key_extractor)
    c.serve_conversation()
    
Since there is a simple anti-bot protection, script that defeats it is not published to prevent spam attacks.
chat_key_extractor is used by Chatter in the following way

    chat_key = chat_key_extractor(script_source)
    
where *script_source* is a raw string containing obfuscated javascript that saves chat key in local variable  *chat_key* after execution.

If you want to modify client behavior, you can inherit from Chatter and overload "on_*event-name*" methods and "idle_proc". 