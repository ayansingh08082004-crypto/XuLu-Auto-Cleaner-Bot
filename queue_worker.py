import asyncio

# =========================================================
# PER USER QUEUES
# =========================================================

user_queues = {}
user_workers = {}


def get_user_queue(user_id):

    if user_id not in user_queues:
        user_queues[user_id] = asyncio.Queue()

    return user_queues[user_id]


# =========================================================
# USER WORKER
# =========================================================

async def user_worker(user_id, process_function):

    q = get_user_queue(user_id)

    while True:

        # Wait for first message
        first_msg = await q.get()

        batch = [first_msg]

        try:

            # -------------------------------------------------
            # SMALL BUFFER
            # Give Telegram time to deliver the next files
            # -------------------------------------------------

            await asyncio.sleep(0.15)

            # -------------------------------------------------
            # Collect all currently waiting messages
            # -------------------------------------------------

            while not q.empty():

                try:
                    next_msg = q.get_nowait()
                    batch.append(next_msg)

                except asyncio.QueueEmpty:
                    break

            # -------------------------------------------------
            # IMPORTANT:
            # Sort by Telegram message_id
            # -------------------------------------------------

            batch.sort(
                key=lambda msg: msg.message_id
            )

            # -------------------------------------------------
            # Process in exact order
            # -------------------------------------------------

            for msg in batch:

                try:

                    await process_function(msg)

                except Exception as e:

                    print(
                        f"Process error "
                        f"[user={user_id}, "
                        f"message={msg.message_id}]: {e}"
                    )

                finally:

                    q.task_done()

                # Keep your order-stability delay
                await asyncio.sleep(0.4)

        except Exception as e:

            print(
                f"Queue worker error [{user_id}]:",
                e
            )

            # Make sure remaining batch items
            # are marked completed
            for _ in batch:
                try:
                    q.task_done()
                except Exception:
                    pass


# =========================================================
# ADD MESSAGE TO USER QUEUE
# =========================================================

async def add_to_queue(msg, process_function):

    user_id = msg.from_user.id

    q = get_user_queue(user_id)

    # -----------------------------------------------------
    # Only ONE worker per user
    # -----------------------------------------------------

    if user_id not in user_workers:

        user_workers[user_id] = asyncio.create_task(
            user_worker(
                user_id,
                process_function
            )
        )

    # -----------------------------------------------------
    # Add message to FIFO queue
    # -----------------------------------------------------

    await q.put(msg)
