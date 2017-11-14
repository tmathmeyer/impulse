#!/bin/bash
zip impulse.zip *.py
echo '#!/usr/bin/env python' | cat - impulse.zip > impulse
chmod +x impulse
