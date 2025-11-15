# cloudlab-bypass-356

## Set-Up Instructions
Step 1: Install dependencies

Run this command to install all prerequisites:

sudo apt update

sudo apt install -y autotools-dev protobuf-compiler libprotobuf-dev dh-autoreconf \
iptables pkg-config dnsmasq-base apache2-bin apache2-dev debhelper \
libssl-dev ssl-cert libxcb-present-dev libcairo2-dev libpango1.0-dev git build-essential

=========================
Step 2: Clone the Mahimahi repo
git clone https://github.com/ravinet/mahimahi.git
cd mahimahi

=========================
Step 3: Patch the C++ flags

Mahimahi’s configure.ac has flags -Wall -Wextra that break with newer GCC.
Edit line 15 of configure.ac to remove them:

nano configure.ac

Look for something like:
PICKY CXXFLAGS="-Wall -Wextra -pedantic -Weffc++"

Change it to:
PICKY CXXFLAGS="-pedantic -Weffc++"

Save and exit (Ctrl+O, Enter, Ctrl+X in nano).

=========================
Step 4: Build and install
Run the usual autotools commands:
./autogen.sh
./configure
make
sudo make install

After this, binaries like `mm-delay` and `mm-link` should be in your path. You can check with:

which mm-delay
which mm-link

=========================
Step 5: Install xvfb
`sudo apt update`
`sudo apt install xvfb`

Then, we can now run Mahimahi like so:
```
xvfb-run -a mm-delay 10 mm-link --meter-uplink --meter-uplink-delay \
--downlink-queue=infinite --uplink-queue=droptail \
--uplink-queue-args=bytes=30000 12mbps 12mbps
```

Notes:
-a automatically chooses a free display number.
The rest of your Mahimahi command stays exactly the same.

=========================
Step 6: Create a link trace file

If you want a 12 Mbit/s link:

echo 1 > 12mbps


1 line = 12 Mbit/s

For 6 Mbit/s, put 2 in the file.

For 24 Mbit/s, put 1 twice.

## Running the Code

### Running Without Emulator (Like Assignment 3)
Added files from previous assignment:
`test_file.txt`
`generate_bogus_text.py`

python3 generate_bogus_text.py 1000000 > test_file.txt 
python3 transport.py --ip localhost --port 7000 receiver
python3 transport.py --ip localhost --port 7000 --sendfile test_file.txt sender

### Running With Emulator (Change `localhost`)
Find out the host `ip address` by running `ip addr` (check for anything that is not `lo` - that's localhost).

Or, you can run `hostname -I` and get the first IP address that is not `127.0.0.1` - that's loopback or localhost.

// For the receiver (this should be done outside the mahi mahi shell):
// We want to detatch the receiver to allow the sender to run in the same terminal
`python3 transport.py --ip 0.0.0.0 --port 7000 receiver &`

To see this process later (to kill it):
`ps aux | grep transport.py`
`kill 39033`

To start the mahimahi shell, run
```
xvfb-run -a mm-delay 10 mm-link --meter-uplink --meter-uplink-delay \
--downlink-queue=infinite --uplink-queue=droptail \
--uplink-queue-args=bytes=30000 12mbps 12mbps
```

// For the sender (this should be done inside the mahi mahi shell):
`python3 transport.py --ip 10.0.0.1 --port 7000 --sendfile test_file.txt sender`

// For running the `goodput_sender.py`, run
`python3 goodput_sender.py --ip 10.0.0.1 --port 7000 --sendfile test_file.txt sender`

// Make sure to use `10.0.0.1` with the actual host IP obtained above inside the shell.
