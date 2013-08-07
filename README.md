chatvdvoem-client
=================

Chatvdvoem client library

Since there is a simple anti-bot protection, script that defeats it is not published, you will have to write your own.
It is called from main module in this way:
    import chatkey
    chat_key = chatkey.get_chat_key(script_source)
where *script_source* is a raw string containing obfuscated javascript that saves chat key in local variable  *chat_key* after execution.

Example usage:

    from chatvdvoem import Chatter
    c = Chatter()
    c.serve_conversation()
    
If you want to modify client behaviour, you can inherit from Chatter and overload "on_*event-name*" methods and "idle_proc". 