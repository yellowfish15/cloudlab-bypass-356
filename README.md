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
Step 5: Create a link trace file

If you want a 12 Mbit/s link:

echo 1 > 12mbps


1 line = 12 Mbit/s

For 6 Mbit/s, put 2 in the file.

For 24 Mbit/s, put 1 twice.