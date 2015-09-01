import time
import itarget_connection
import iserial_like


class SerialConnection(itarget_connection.ITargetConnection):
    """
    ITargetConnection implementation for generic serial ports.
    Designed to utilize SerialConnectionLowLevel (see __init__).

    Since serial ports provide no default functionality for separating messages/packets, this class provides
    several means:
     - timeout: Return received bytes after timeout seconds.
     - msg_separator_time:
                Return received bytes after the wire is silent for a given time.
                This is useful, e.g., for terminal protocols without a machine-readable delimiter.
                A response may take a long time to send its information, and you know the message is done
                when data stops coming.
     - content_check:
                A user-defined function takes the data received so far and checks for a packet.
                The function should return 0 if the packet isn't finished yet, or n if a valid message of n
                bytes has been received. Remaining bytes are stored for next call to recv().

                Example:
                def content_check_newline(data):
                  if data.find('\n') >= 0:
                    return data.find('\n')
                  else:
                    return 0
    If none of these methods are used, your connection may hang forever.
    """

    def __init__(self, connection, timeout=None, message_separator_time=None, content_checker=None):
        """
        @type  connection:             iserial_like.ISerialLike
        @param connection:             Low level connection, e.g., SerialConnectionLowLevel.
        @type timeout:                 float
        @param timeout:                For recv(). After timeout seconds from receive start,
                                       recv() will return all received data, if any.
        @type message_separator_time:  float
        @param message_separator_time: (Optional, def=None)
                                       After message_separator_time seconds _without receiving any more data_,
                                       recv() will return.
        @type content_checker:         function(str) -> int
        @param content_checker:        (Optional, def=None) User-defined function.
                                           recv() will pass all bytes received so far to this method.
                                           If the method returns n > 0, recv() will return n bytes.
                                           If it returns 0, recv() will keep on reading.
        """
        self._connection = connection
        self._logger = None
        self.timeout = timeout
        self.message_separator_time = message_separator_time
        self.content_checker = content_checker

        self._leftover_bytes = b''

    def close(self):
        """
        Close connection to the target.

        :return: None
        """
        self._connection.close()

    def open(self):
        """
        Opens connection to the target. Make sure to call close!

        :return: None
        """
        self._connection.open()

    def recv(self, max_bytes):
        """
        Receive up to max_bytes data from the target.

        :param max_bytes: Maximum number of bytes to receive.
        :type max_bytes: int

        :return: Received data.
        """

        self._connection.timeout = min(.001, self.message_separator_time, self.timeout)

        start_time = last_byte_time = time.time()

        data = self._leftover_bytes
        self._leftover_bytes = b''

        while len(data) < max_bytes:
            # Update timer for message_separator_time
            if len(data) > 0:
                last_byte_time = time.time()

            # Try recv again
            fragment = self._connection.recv(max_bytes=max_bytes-len(data))
            data += fragment

            # User-supplied content_checker function
            if self.content_checker is not None:
                num_valid_bytes = self.content_checker(data)
                if num_valid_bytes > 0:
                    self._leftover_bytes = data[num_valid_bytes:]
                    return data[0:num_valid_bytes]

            # Check timeout and message_separator_time
            cur_time = time.time()
            if self.timeout is not None and cur_time - start_time >= self.timeout:
                return data
            if self.message_separator_time is not None and cur_time - last_byte_time >= self.message_separator_time:
                return data

        return data

    def send(self, data):
        """
        Send data to the target. Only valid after calling open!

        :param data: Data to send.

        :return: None
        """
        bytes_sent = 0
        while bytes_sent < len(data):
            bytes_sent_this_round = self._connection.send(data[bytes_sent:])
            if bytes_sent_this_round is not None:
                bytes_sent += bytes_sent_this_round
        return bytes_sent

    def set_logger(self, logger):
        """
        Set this object's (and it's aggregated classes') logger.

        :param logger: Logger to use.
        :type logger: logging.Logger

        :return: None
        """
        self._logger = logger
